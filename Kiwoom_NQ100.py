import sys
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from PyQt5 import uic
import time as t
import datetime
import pandas as pd
import numpy as np
pd.options.mode.chained_assignment = None
import pandas_ta as ta
import sqlite3


main_form = uic.loadUiType("MainWindow2.ui")[0]

class Window(QMainWindow, main_form):
    def __init__(self, hts):
        super().__init__()
        self.hts = hts
        self.setupUi(self)
        self.set_event_handler()

    def set_event_handler(self):
        #self.testButton.clicked.connect(self.hts.test)

        # 메뉴바
        # Tools
        #self.action_ohlcv_save.triggered.connect(self.hts.action_real_chart_save)
        #self.action_tick_chart_req.triggered.connect(self.hts.action_tick_chart_req)

        # 테스트 버튼
        #self.pushButton.clicked.connect(self.hts.actionbt)
        #self.pushButton.clicked.connect(self.hts.action_buy)
        #self.pushButton_2.clicked.connect(self.hts.action_sell)
        #self.pushButton_3.clicked.connect(self.hts.action_close)
        #self.pushButton_4.clicked.connect(self.hts.action_start)
        #self.pushButton_5.clicked.connect(self.hts.action_end)
        pass


class Kiwoom_NQ100(QAxWidget):
    def __init__(self):
        super().__init__()
        self._create_kiwoom_instance()
        self._set_signal_slots()

        self.comm_connect()

        # 계좌정보
        account_numbers = self.get_login_info("ACCNO")
        self.future_accno = account_numbers.split(';')[0]  # 7011576372

        self.ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume'])

        # 실시간 틱차트 (t : tick, c = current)
        self.cnt = 0
        self.base_tick_unit = 120
        #self.base_tick_unit = 10
        self.code_symbol = "NQM24"  # MNQZ23
        self.t_cnt = 0
        self.c_dt = 0
        self.c_close = 0
        self.c_high = 0
        self.c_low = 0
        self.c_open = 0
        self.c_volume = 0

        # 선물틱차트조회
        self.set_input_value("종목코드", self.code_symbol)
        self.set_input_value("시간단위", self.base_tick_unit)
        self.comm_rq_data("해외선물틱차트조회", "opc10001", '', "2000")


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
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def on_event_connect(self, err_code):
        if err_code == 0:
            print("connected")
        else:
            print("disconnected")

        self.login_event_loop.exit()

    def get_login_info(self, tag):
        ret = self.dynamicCall("GetLoginInfo(QString)", tag)
        return ret

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_rq_data(self, rqname, trcode, next, screen_no):
        self.dynamicCall("CommRqData(QString, QString, QString, QString)", rqname, trcode, next, screen_no)

    def _comm_get_data(self, sTrCode, sRQName, index, item_name):
        ret = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode,
                               sRQName, index, item_name)
        return ret.strip()

    def _get_repeat_cnt(self, trcode, rqname):
        ret = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        return ret

    def _get_comm_real_data(self, sCode, sRealType):
        ret = self.dynamicCall("GetCommRealData(QString, int)", sCode, sRealType) # 체결 시간
        return ret.strip()

    def on_receive_tr_data(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):

        print('== on_receive_tr_data ==')
        print(sRQName)

        if sRQName == '해외선물틱차트조회':

            # 시작 시간
            start_dt = datetime.datetime.today()

            print(f"해외선물틱차트조회 시작!")



            last_tick_cnt = self._comm_get_data(sTrCode, sRQName, 0, "최종틱갯수")
            self.t_cnt = int(last_tick_cnt)

            print(f"최종틱갯수: {self.t_cnt}")

            # 마지막(현재) 캔들 읽어 오기
            self.c_dt = pd.to_datetime(self._comm_get_data(sTrCode, sRQName, 0, "체결시간"))
            self.c_open = abs(float(self._comm_get_data(sTrCode, sRQName, 0, "시가")))
            self.c_high = abs(float(self._comm_get_data(sTrCode, sRQName, 0, "고가")))
            self.c_low = abs(float(self._comm_get_data(sTrCode, sRQName, 0, "저가")))
            self.c_close = abs(float(self._comm_get_data(sTrCode, sRQName, 0, "현재가")))
            self.c_volume = abs(int(self._comm_get_data(sTrCode, sRQName, 0, "거래량")))

            if self.t_cnt == 0:
                # ohlcv에 맨앞에 추가
                ohlcv = pd.DataFrame(
                    {'date_time': self.c_dt, 'Open': self.c_open, 'High': self.c_high, \
                     'Low': self.c_low, 'Close': self.c_close, 'Volume': self.c_volume}, index=[0])
                self.ohlcv = pd.concat([ohlcv, self.ohlcv], ignore_index=True)

                # 초기화
                self.c_open = 0
                self.c_high = 0
                self.c_low = 10000000
                self.c_close = 0
                self.c_volume = 0

            data_cnt = self._get_repeat_cnt(sTrCode, sRQName)

            for i in range(1, data_cnt):
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

                self.ohlcv = pd.concat([ohlcv, self.ohlcv], ignore_index=True)

            # 종료 시간
            end_dt = datetime.datetime.today()

            # 실행 시간
            delta = (end_dt - start_dt).total_seconds()

            print(f"해외선물틱차트조회 끝!")
            print(f"({delta}초 = {end_dt} - {start_dt})")

    def on_receive_chejan_data(self, sGubun, nItemCnt, sFidList):
        #pass
        # self.get_current_position()
        print('== on_receive_chejan_data ==')

    def on_receive_real_data(self, sCode, sRealType, sRealData):

        if sRealType == '해외선물시세':
            #print(sRealData)

            c_dt = datetime.datetime.today()

            # 틱카운트 증가 (+1)
            self.t_cnt += 1

            n_time = self._get_comm_real_data(sCode, 20)  # 체결 시간
            n_date = self._get_comm_real_data(sCode, 22)  # 체결 일자
            n_dt = pd.to_datetime(n_date + n_time)

            c_price = abs(float(self._get_comm_real_data(sCode, 10)))  # 현재가(체결가)
            c_volume = abs(int(self._get_comm_real_data(sCode, 15)))  # 거래량 (+ 매수체결, - 매도체결)

            #print(f"[1틱-{self.t_cnt}] 체결시간: {n_dt}, 체결시간2: {c_dt}, 체결가: {c_price}, 거래량: {c_volume}")


            # 첫번째 틱일 경우, 체결 시간(일시)과 시가 업데이트
            if self.t_cnt == 1:
                self.c_open = c_price
                self.c_dt = n_dt

            # 고가와 저가 업데이트
            if self.c_high < c_price:
                self.c_high = c_price
            if self.c_low > c_price:
                self.c_low = c_price

            # 종가와 거래량 업데이트
            self.c_close = c_price
            self.c_volume += c_volume

            if self.t_cnt == self.base_tick_unit:
                ohlcv = pd.DataFrame(
                    {'date_time': self.c_dt, 'Open': self.c_open, 'High': self.c_high,'Low': self.c_low, 'Close': self.c_close, 'Volume': self.c_volume}, index=[0])
                self.ohlcv = pd.concat([self.ohlcv, ohlcv], ignore_index=True)

                print(f"[120틱-{self.ohlcv.index[-1]}] 체결시간: {self.ohlcv.date_time.iloc[-1]}, "
                      f"시가: {self.ohlcv.Open.iloc[-1]}, 고가: {self.ohlcv.High.iloc[-1]}, 저가: {self.ohlcv.Low.iloc[-1]}, 종가: {self.ohlcv.Close.iloc[-1]}, 거래량: {self.ohlcv.Volume.iloc[-1]}")

                # 초기화
                self.c_open = 0
                self.c_high = 0
                self.c_low = 10000000
                self.c_close = 0
                self.c_volume = 0
                self.t_cnt = 0



        pass

    def on_receive_msg(self, screen_number, rq_name, tr_code, msg):

        print('== on_receive_msg ==')
        print(f'{rq_name}, {msg}')


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        hts = Kiwoom_NQ100()
        window = Window(hts)
        window.show()
        sys.exit( app.exec_() )
    except Exception as e:
        print(e)

