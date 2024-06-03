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

        self.pushButton_4.clicked.connect(self.hts.action_start)
        self.pushButton_5.clicked.connect(self.hts.action_end)

        # 1. 시장가
        self.pushButton.clicked.connect(self.hts.action_buy)
        self.pushButton_2.clicked.connect(self.hts.action_sell)
        self.pushButton_3.clicked.connect(self.hts.action_close)

        # 2.지정가
        self.pushButton_6.clicked.connect(self.hts.action_buy2)
        self.pushButton_7.clicked.connect(self.hts.action_sell2)

        # 3.STOP
        self.pushButton_8.clicked.connect(self.hts.action_buy3)
        self.pushButton_9.clicked.connect(self.hts.action_sell3)

        # 4.StopLimit
        self.pushButton_10.clicked.connect(self.hts.action_buy4)
        self.pushButton_11.clicked.connect(self.hts.action_sell4)

        # 5.OCO
        self.pushButton_12.clicked.connect(self.hts.action_buy5)
        self.pushButton_13.clicked.connect(self.hts.action_sell5)

        # 6.IFD
        self.pushButton_14.clicked.connect(self.hts.action_buy6)
        self.pushButton_15.clicked.connect(self.hts.action_sell6)

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
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N'])

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

        self._system_running = False

        # 스크린 번호
        self.screen_number = 1000

        # 터틀 트레이딩
        self.atr_periods = 20
        self.sys1_entry = 20
        self.sys1_exit = 10

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

    def on_receive_msg(self, screen_number, rq_name, tr_code, msg):

        print('== on_receive_msg ==')
        print(f'{rq_name}, {msg}')

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

                # Breakouts과 N계산
                df = self.ohlcv[-30:]
                df = self._calc_breakouts(df)
                df = self._calc_N(df)

                # ohlcv에 시스템 1의 Breakouts 추가
                self.ohlcv.S1_EL.iloc[-1] = df.S1_EL.iloc[-1]
                self.ohlcv.S1_ES.iloc[-1] = df.S1_ES.iloc[-1]
                self.ohlcv.S1_ExL.iloc[-1] = df.S1_ExL.iloc[-1]
                self.ohlcv.S1_ExS.iloc[-1] = df.S1_ExS.iloc[-1]

                # ohlcv에 N과 V(속도) 추가
                self.ohlcv.N.iloc[-1] = df.N.iloc[-1]

                print(f"[120틱-{self.ohlcv.index[-1]}] 체결시간: {self.ohlcv.date_time.iloc[-1]}, "
                      f"시가: {self.ohlcv.Open.iloc[-1]}, 고가: {self.ohlcv.High.iloc[-1]}, 저가: {self.ohlcv.Low.iloc[-1]}, 종가: {self.ohlcv.Close.iloc[-1]}, 거래량: {self.ohlcv.Volume.iloc[-1]}")

                # 초기화
                self.c_open = 0
                self.c_high = 0
                self.c_low = 10000000
                self.c_close = 0
                self.c_volume = 0
                self.t_cnt = 0

                if self._system_running:
                    self._run_system()


        pass

    def _run_system(self):

        price = self.ohlcv.Close.iloc[-1]

        # 시스템 1
        S1_EL = self.ohlcv.S1_EL.iloc[-1]
        S1_ES = self.ohlcv.S1_ES.iloc[-1]

        S1_ExL = self.ohlcv.S1_ExL.iloc[-1]
        S1_ExS = self.ohlcv.S1_ExS.iloc[-1]

        N = self.ohlcv.N.iloc[-1]

        print(f"_run_system")

        pass

    def _calc_breakouts(self, df):

        # 시스템 1
        df['S1_EL'] = df['Close'].rolling(self.sys1_entry).max()
        df['S1_ExL'] = df['Close'].rolling(self.sys1_exit).min()
        df['S1_ES'] = df['Close'].rolling(self.sys1_entry).min()
        df['S1_ExS'] = df['Close'].rolling(self.sys1_exit).max()

        return df

    def _calc_N(self, df):

        df['N'] = ta.atr(df['High'], df['Low'], df['Close'], length=20, mamode='sma')

        return df

    def get_screen_number(self):
        if self.screen_number > 9999:
            self.screen_number = 1000
        self.screen_number = self.screen_number + 1
        return str(self.screen_number)

    """
    [opw10008: 해외파생신규주문2]

    1. OpenAPI 조회 함수 입력값을 (설정합니다.
                           
    SetInputValue("계좌번호", "입력값1"));

    SetInputValue("비밀번호", "입력값2");

    비밀번호입력매체 = 00
    입력
    SetInputValue("비밀번호입력매체", "입력값3");

    SetInputValue("종목코드", "입력값4");

    매도수구분 = 1:매도, 2: 매수
    SetInputValue("매도수구분", "입력값5");

    해외주문유형 = 1:시장가, 2: 지정가, 3: STOP, 4: StopLimit, 5: OCO, 6: IF
    DONE
    SetInputValue("해외주문유형", "입력값6");

    SetInputValue("주문수량", "입력값7");

    SetInputValue("주문표시가격", "입력값8");

    STOP구분 = 0:선택안함, 1: 선택
    SetInputValue("STOP구분", "입력값9");

    SetInputValue("STOP표시가격", "입력값10");

    LIMIT구분 = 0:선택안함, 1: 선택
    SetInputValue("LIMIT구분", "입력값11");

    SetInputValue("LIMIT표시가격", "입력값12");

    해외주문조건구분 = 0:당일, 6: GTD
    SetInputValue("해외주문조건구분", "입력값13");

    주문조건종료일자 = "":당일(0), 날짜입력: GTD(6)
    SetInputValue("주문조건종료일자", "입력값14");

    통신주문구분 = "AP"
    입력
    SetInputValue("통신주문구분", "입력값15");
  
    2. OpenAPI조회 함수를 호출해서 전문을 서버로 전송합니다.
    CommRqData("RQName", "opw10008", "", "화면번호");

    """


    def send_order2(self, account_num, password, code, ls_gb, order_type, qty, price, stop_gb, stop_price, limit_gb, limit_price):
        self.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_num)
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호", password)
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체", "00")
        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("SetInputValue(QString, QString)", "매도수구분", ls_gb)  # 1: 매도, 2: 매수
        self.dynamicCall("SetInputValue(QString, QString)", "해외주문유형", order_type)  # 1: 시장가, 2: 지정가, ...
        self.dynamicCall("SetInputValue(QString, QString)", "주문수량", str(qty))
        self.dynamicCall("SetInputValue(QString, QString)", "주문표시가격", str(price))
        self.dynamicCall("SetInputValue(QString, QString)", "STOP구분", str(stop_gb))
        self.dynamicCall("SetInputValue(QString, QString)", "STOP표시가격", str(stop_price))
        self.dynamicCall("SetInputValue(QString, QString)", "LIMIT구분", str(limit_gb))
        self.dynamicCall("SetInputValue(QString, QString)", "LIMIT표시가격", str(limit_price))
        self.dynamicCall("SetInputValue(QString, QString)", "해외주문조건구분", "0")  # 0: 당일, 6: GTD
        self.dynamicCall("SetInputValue(QString, QString)", "주문조건종료일자", "")
        self.dynamicCall("SetInputValue(QString, QString)", "통신주문구분", "AP")

        self.dynamicCall("CommRqData(QString, QString, int, QString)", "해외파생신규주문2", "opw10008", "", self.get_screen_number())       #self.order_event_loop.exec_()

    def get_order_gb(self, type):
        if type == '매도':
            return '1'
        elif type == '매수':
            return '2'

    def get_order_type(self, type):
        if type == '시장가':
            return '1'
        elif type == '지정가':
            return '2'
        elif type == 'STOP':
            return '3'
        elif type == 'StopLimit':
            return '4'
        elif type == 'OCO':
            return '5'
        elif type == 'IFD':
            return '6'


############# 테스트 버튼 action ################

    def action_start(self):
        QMessageBox.about(self, "message", "start")

        self._system_running = True

    def action_end(self):
        QMessageBox.about(self, "message", "end")

        self._system_running = False

    def action_buy(self):
        QMessageBox.about(self, "message", "시장가 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('시장가'), 1, '', \
                        '0', '', '0', '')

    def action_sell(self):
        QMessageBox.about(self, "message", "시장가 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('시장가'), 1, '', \
                        '0', '', '0', '')

    def action_buy2(self):
        QMessageBox.about(self, "message", "지정가 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('지정가'), 1, self.c_close, \
                        '0', '', '0', '')

    def action_sell2(self):
        QMessageBox.about(self, "message", "지정가 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('지정가'), 1, self.c_close, \
                        '0', '', '0', '')

    def action_buy3(self):
        QMessageBox.about(self, "message", "STOP 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('STOP'), 1, '', \
                        '1', self.c_close+5, '0', '')

    def action_sell3(self):
        QMessageBox.about(self, "message", "STOP 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('STOP'), 1, '', \
                        '1', self.c_close-5, '0', '')

    def action_buy4(self):
        QMessageBox.about(self, "message", "StopLimit 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('StopLimit'), 1, self.c_close+5.5, \
                        '1', self.c_close+5, '0', '')

    def action_sell4(self):
        QMessageBox.about(self, "message", "StopLimit 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('StopLimit'), 1, self.c_close-5.5, \
                        '1', self.c_close-5, '0', '')


    def action_buy5(self):
        QMessageBox.about(self, "message", "OCO 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('OCO'), 1, '', \
                        '1', self.c_close+5, '1', self.c_close-5)

    def action_sell5(self):
        QMessageBox.about(self, "message", "OCO 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('OCO'), 1, '', \
                        '1', self.c_close-5, '1', self.c_close+5)

    def action_buy6(self):
        QMessageBox.about(self, "message", "IFD 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('IFD'),
                         1, self.c_close, \
                         '1', self.c_close - 5, '1', self.c_close + 5)

    def action_sell6(self):
        QMessageBox.about(self, "message", "IFD 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('IFD'),
                         1, self.c_close, \
                         '1', self.c_close + 5, '1', self.c_close - 5)

    def action_close(self):
        QMessageBox.about(self, "message", "position close")

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        hts = Kiwoom_NQ100()
        window = Window(hts)
        window.show()
        sys.exit( app.exec_() )
    except Exception as e:
        print(e)

