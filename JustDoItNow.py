import sys
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5 import uic
import time as t
from datetime import datetime
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None
import pandas_ta as ta
import sqlite3

main_form = uic.loadUiType("MainWindow3.ui")[0]

class Broker(QAxWidget):

    def __init__(self, mainwindow,
                 ticker="MNQM24",
                 tick_unit=120
                 ):
        super().__init__()

        #QMessageBox.about(self, "message", "Broker.__init__")

        self.mw = mainwindow
        self._create_kiwoom_instance()
        self._set_signal_slots()

        # 키움 서버 접속
        self.connected = False  # for login event

        # 이벤트 루프
        self.login_event_loop = QEventLoop()

        # 스크린 번호
        self.screen_number = 1000

        # 종목코드
        self.ticker = ticker  # MNQZ23

        # 실시간 차트 시간단위
        self.tick_unit = tick_unit
        self.t_cnt = 0

        # 차트
        self.t_ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N'])


    def _create_kiwoom_instance(self):
        self.setControl("KFOPENAPI.KFOpenAPICtrl.1")

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self.on_event_connect)
        self.OnReceiveTrData.connect(self.on_receive_tr_data)
        self.OnReceiveChejanData.connect(self.on_receive_chejan_data)
        self.OnReceiveRealData.connect(self.on_receive_real_data)
        self.OnReceiveMsg.connect(self.on_receive_msg)

    def comm_connect(self):
        self.dynamicCall("CommConnect(int)", 1)
        self.login_event_loop.exec_()


    def on_event_connect(self, err_code):

        #QMessageBox.about(self, "message", "on_event_connect()")

        if err_code == 0:

            self.connected = True
            print("connected")

        else:

            self.connected = False
            print("disconnected")


        self.login_event_loop.exit()

    def set_account_num(self):

        ret = self.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        self.accno = ret.split(';')[0]

        pass

    def req_opc10001(self):

        # 선물분차트조회
        self.set_input_value("종목코드", self.ticker)
        self.set_input_value("시간단위", self.tick_unit)
        self.comm_rq_data("틱차트조회", "opc10001", '', self.get_screen_number())

        pass

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)


    def comm_rq_data(self, rqname, trcode, next, screen_no):
        ret = self.dynamicCall("CommRqData(QString, QString, QString, QString)", rqname, trcode, next, screen_no)
        return ret

    def get_screen_number(self):

        if self.screen_number > 9999:
            self.screen_number = 1000

        self.screen_number = self.screen_number + 1

        return str(self.screen_number)

    def _get_repeat_cnt(self, trcode, rqname):
        ret = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        return ret

    def _comm_get_data(self, sTrCode, sRQName, index, item_name):
        ret = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                               sRQName, index, item_name)
        return ret.strip()


    def on_receive_tr_data(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):

        if sRQName == '틱차트조회':

            # 조회 시작 시간
            start_dt = datetime.today()

            print(f"{self.tick_unit}틱차트 조회 시작!")

            self.t_cnt = int(self._comm_get_data(sTrCode, sRQName, 0, "최종틱갯수"))

            print(f"최종틱갯수: {self.t_cnt}")

            data_cnt = self._get_repeat_cnt(sTrCode, sRQName)

            #for i in range(0, data_cnt):
            for i in range(0, 100):
                dt = pd.to_datetime(self._comm_get_data(sTrCode, sRQName, i, "체결시간"))
                open = abs(float(self._comm_get_data(sTrCode, sRQName, i, "시가")))
                high = abs(float(self._comm_get_data(sTrCode, sRQName, i, "고가")))
                low = abs(float(self._comm_get_data(sTrCode, sRQName, i, "저가")))
                close = abs(float(self._comm_get_data(sTrCode, sRQName, i, "현재가")))
                volume = abs(int(self._comm_get_data(sTrCode, sRQName, i, "거래량")))
                volume = abs(int(volume))

                ohlcv = pd.DataFrame(
                    {'date_time': dt, 'Open': open, 'High': high, 'Low': low, 'Close': close,
                     'Volume': volume}, index=[0])

                self.t_ohlcv = pd.concat([ohlcv, self.t_ohlcv], ignore_index=True)


            print(f"{self.tick_unit}틱차트 조회 끝!")

            # 종료 시간
            end_dt = datetime.today()

            # 실행 시간
            delta = (end_dt - start_dt).total_seconds()

            print(f"({delta}초 = {end_dt} - {start_dt})")

        pass

    def on_receive_chejan_data(self, sGubun, nItemCnt, sFidList):
        pass

    def _get_comm_real_data(self, sCode, sRealType):
        ret = self.dynamicCall("GetCommRealData(QString, int)", sCode, sRealType) # 체결 시간
        return ret.strip()

    def on_receive_real_data(self, sCode, sRealType, sRealData):

        if sRealType == '해외선물시세':
            # print(sRealData)

            n_time = self._get_comm_real_data(sCode, 20)  # 체결 시간
            n_date = self._get_comm_real_data(sCode, 22)  # 체결 일자
            n_dt = pd.to_datetime(n_date + n_time)

            dt = self.t_ohlcv.date_time.iloc[-1]
            delta = n_dt.minute - dt.minute

            c_price = abs(float(self._get_comm_real_data(sCode, 10)))  # 현재가(체결가)
            c_volume = abs(int(self._get_comm_real_data(sCode, 15)))  # 거래량 (+ 매수체결, - 매도체결)

            # 틱 카운트 +1 증가
            # 1(시가),2,3,4,0(종가)
            self.t_cnt += 1

            gb = self.t_cnt % self.tick_unit

            # 1: 새틱차트 생성
            # 새틱차트 시작, 새틱차트 생성
            if gb == 1:

                # print(f"틱 카운트: {self.t_cnt}, 구분: {gb}, 새틱차트 생성, 시작시간: {c_dt}, 시가(현재가): {c_price:.2f}, 시작수량: {c_volume} ")

                ohlcv = pd.DataFrame(
                    {'date_time': n_dt, 'Open': c_price, 'High': 0, 'Low': 100000,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.t_ohlcv = pd.concat([self.t_ohlcv, ohlcv], ignore_index=True)

                # 마지막차트 출력
                print(f"[{self.tick_unit}틱-{self.t_ohlcv.index[-2]}] 체결시간: {self.t_ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.t_ohlcv.Open.iloc[-2]:.2f}, 고가: {self.t_ohlcv.High.iloc[-2]:.2f}, 저가: {self.t_ohlcv.Low.iloc[-2]:.2f}, 종가: {self.t_ohlcv.Close.iloc[-2]:.2f}, 거래량: {self.t_ohlcv.Volume.iloc[-2]}")


            # 2,3,4,0: 기존차트에서 틱업데이트
            else:

                # 고가와 저가 업데이트

                if self.t_ohlcv.High.iloc[-1] < c_price:
                    self.t_ohlcv.High.iloc[-1] = c_price
                if self.t_ohlcv.Low.iloc[-1] > c_price:
                    self.t_ohlcv.Low.iloc[-1] = c_price

                # 종가와 거래량 업데이트
                self.t_ohlcv.Close.iloc[-1] = c_price
                self.t_ohlcv.Volume.iloc[-1] += c_volume

        pass

    def on_receive_msg(self, screen_number, rq_name, tr_code, msg):
        pass


class Fire(QMainWindow, main_form):

    def __init__(self):
        super().__init__()

        #QMessageBox.about(self, "message", "Fire.__init__")

        self.setupUi(self)
        self.set_event_handler()

        # Broker 인스턴스 생성
        self.kiwoom = Broker(self, "MNQM24", 120)

        # 키움서버 접속
        self.kiwoom.comm_connect()

        # 계좌번호 설정
        self.kiwoom.set_account_num()

        # 틱차트 요청
        self.kiwoom.req_opc10001()

    def set_event_handler(self):
        pass


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        window = Fire()
        window.show()

        sys.exit( app.exec_() )
    except Exception as e:
        print(e)


