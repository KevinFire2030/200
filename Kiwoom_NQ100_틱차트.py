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


main_form = uic.loadUiType("MainWindow2.ui")[0]

class Window(QMainWindow, main_form):
    def __init__(self, hts):
        super().__init__()
        self.hts = hts
        self.setupUi(self)
        self.set_event_handler()

        self.hts.mw = self

        self.statusBar().showMessage(self.hts.comm_status)


    def set_event_handler(self):
        #self.testButton.clicked.connect(self.hts.test)

        # 메뉴바
        # Tools
        #self.action_ohlcv_save.triggered.connect(self.hts.action_real_chart_save)
        #self.action_tick_chart_req.triggered.connect(self.hts.action_tick_chart_req)
        self.connect_status.triggered.connect(self.action_connect_status)
        self.req_opw30003.triggered.connect(self.hts.req_opw30003)

        # 시작 종료 버튼
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

        # line edit
        self.lineEdit.textChanged.connect(self.changeTextFunction)

        # 포지션 일괄 청산
        self.pushButton_3.clicked.connect(self.hts.position.close)

        pass

    def changeTextFunction(self):
        # self.lineedit이름.setText("String")
        # Lineedit의 글자를 바꾸는 메서드
        self.label_7.setText(self.lineEdit.text())

    def action_connect_status(self):

        self.statusBar().showMessage(self.hts.comm_status)

class Position:
    def __init__(self, broker: 'Kiwoom_NQ100'):
        self.__broker = broker

        # OnReceiveTrData() 함수에서 req_opw30003() 요청에 대한 Tr 수신시  업데이트 변수
        # 청산시 초기화
        self.code = '' # 종목이 여러 종목 일수 있지만 일단 단일종목만
        self.gb = 0 # 1: 매도, 2: 매수, 0: 포지션x
        self.qty = 0 # 수량
        self.d_qty = 0 # 청산(처분)가능 수량, disposal qty
        self.a_price = 0 # 평단가, average price
        self.commission = 0 # 수수료, 실제 사용하지는 않음
        self.c_pl = 0  # 실현손익(원), closed pl

        # OnReceiveRealData() 함수에서 실시간 업데이트 변수
        self.c_price = 0  # 현재가, current price
        self.pl = 0  # 평가손익($)
        self.pl_KRW = 0  # 평가손익(원)
        self.r_pl = 0  # 실손익($) (= 평가손익 - 수수료), real pl
        self.r_pl_KRW = 0  # 실손익(원) (= r_pl * 환율), won pl
        self.pl_pct = 0 # 수익률


        self.bep = 0 # 본전, 수수료 포함, 평단가 + 수수료 (수량 * 2$)

    def update(self, c_price):
        #print(f"position update()")

        # 포지션이 있는 경우에만 업데이트
        if self.qty > 0:
            # 손익 계산
            # 평단가와 현재가 차이 계산
            p_delta = self.a_price - c_price if self.is_short() else c_price - self.a_price
            # 수량과 레버이지를 곱해 손익 계산
            # 평가(청산) 손익 ($)
            pl = p_delta * self.qty * self.get_point_value(self.code)
            # 평가(청산) 손익 (원)
            pl_KRW = pl * self.get_exRate()
            # 실손익 ($)
            r_pl = pl - self.get_commission() * self.qty
            # 모투 수수료 적용 for 검증
            #r_pl = pl - self.commission * self.qty
            # 실손익 (원)
            r_pl_KRW = r_pl * self.get_exRate()
            # 수익률
            pl_pct = round(p_delta / self.a_price * 100,2)

            # 포지션 업데이트

            self.c_price = c_price # 현재가
            self.pl = pl  # 평가손익($)
            self.pl_KRW = pl_KRW  # 평가손익($)
            self.r_pl = r_pl  # 실손익($) (= 평가손익 - 수수료), real pl
            self.r_pl_KRW = r_pl_KRW  # 실손익(원) (= r_pl * 환율), won pl
            self.pl_pct = pl_pct  # 수익률


        # Main Window 업데이트 - 임시
        # 실시간 체결가 업데이트
        self.__broker.mw.lineEdit_5.setText(str(self.pl_KRW))
        # 실시간 손익 업데이트
        self.__broker.mw.lineEdit_6.setText(str(self.pl))
        # 실시간 손익 업데이트
        self.__broker.mw.lineEdit_7.setText(str(self.pl_pct))

        pass

    def get_exRate(self):

        return self.__broker.exRate

    def get_point_value(self, code):

        if code[0:2] == 'NQ':
            value = 20

        elif code[0:2] == 'MN':
            value = 2

        else:
            value = 1

        return value



    """
    def get_commission(self, code):
           if code[0:2] == 'NQ':
               value = 2.3 * 2 # 왕복 4.6$

           elif code[0:2] == 'MN':
               value = 1 * 2 # # 왕복 2$

           else:
               value = 1
           """

    def get_commission(self):

        return self.__broker.commission * 2 # 왕복, [체결내역-참고] 원화환율: 1377.0, 종목수수료: 2.0

    """
       def action_buy(self):
        QMessageBox.about(self, "message", "시장가 매수")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'), self.get_order_type('시장가'), 1, '', \
                        '0', '', '0', '')

    def action_sell(self):
        QMessageBox.about(self, "message", "시장가 매도")

        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'), self.get_order_type('시장가'), 1, '', \
                        '0', '', '0', '')
    """


    def close(self):
        print(f"position close()")

        # 미체결주문이 있는지 확인
        # 있으면 모두(일괄) 취소

        # 미체결주문이 없고 청산가능 수량이 1 이상인지 확인

        if (self.qty == self.d_qty) and self.d_qty > 0:

            # 매수 포지션이면
            if self.is_long():

                # 시장가 전량 매도
                self.__broker.send_order2(self.__broker.future_accno, "", self.__broker.code_symbol, self.__broker.get_order_gb('매도'), \
                                 self.__broker.get_order_type('시장가'), self.d_qty, '', \
                                 '0', '', '0', '')

            # 매도 포지션이면
            elif self.is_short():

                # 시장가 전량 매수
                self.__broker.send_order2(self.__broker.future_accno, "", self.__broker.code_symbol, self.__broker.get_order_gb('매수'), \
                                          self.__broker.get_order_type('시장가'), self.d_qty, '', \
                                          '0', '', '0', '')


    def is_long(self) -> bool:
        """True if the position is long (self.gb is 2)."""
        return self.gb == 2

    def is_short(self) -> bool:
        #print(f"position is_short()")
        """True if the position is short (self.gb is 1)."""
        return self.gb == 1


class Kiwoom_NQ100(QAxWidget):
    def __init__(self):
        super().__init__()
        self._create_kiwoom_instance()
        self._set_signal_slots()

        self.comm_connect()

        # 계좌정보
        account_numbers = self.get_login_info("ACCNO")
        self.future_accno = account_numbers.split(';')[0]  # 7011576372

        # 포지션
        self.position = Position(self)
        self.exRate = 1
        self.commission = 1


        # 실시간 틱차트 (t : tick, c = current)
        self.ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N'])

        #self.base_min_unit = 5
        self.base_tick_unit = 120
        self.code_symbol = "MNQM24"  # MNQZ23
        self.t_cnt = 0


        # 자동 매매 시작/종료 설정
        self._system_running = False

        # 스크린 번호
        self.screen_number = 1000

        # 터틀 트레이딩
        self.atr_periods = 20
        self.sys1_entry = 20
        self.sys1_exit = 10

        # 체잔 주문/체결 시간
        self.o_dt = 0
        self.t_dt = 0
        self.o_price = 0
        self.t_price = 0

        # 미결제잔고내역조회 (opw30003)
        # 프로그램 시작전에 미결제 잔고가 있는지 확인
        # 잔고가 있으면 포지션 업데이트
        self.req_opw30003()

        # 선물틱차트조회
        self.set_input_value("종목코드", self.code_symbol)
        self.set_input_value("시간단위", self.base_tick_unit)
        self.comm_rq_data("해외선물틱차트조회", "opc10001", '', self.get_screen_number())

        # main window
        self.mw = 0



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
            self.comm_status = "connected"
        else:
            print("disconnected")
            self.comm_status = "disconnected"

        self.login_event_loop.exit()

    def get_login_info(self, tag):
        ret = self.dynamicCall("GetLoginInfo(QString)", tag)
        return ret

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_rq_data(self, rqname, trcode, next, screen_no):
        ret = self.dynamicCall("CommRqData(QString, QString, QString, QString)", rqname, trcode, next, screen_no)
        return ret

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
            start_dt = datetime.today()

            print(f"해외선물 {self.base_tick_unit}틱차트 조회 시작!")


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

                self.ohlcv = pd.concat([ohlcv, self.ohlcv], ignore_index=True)


            # 종료 시간
            end_dt = datetime.today()

            # 실행 시간
            delta = (end_dt - start_dt).total_seconds()

            print(f"해외선물 {self.base_tick_unit}틱차트 조회 끝!")
            print(f"({delta}초 = {end_dt} - {start_dt})")

        elif sRQName == '해외선물분차트조회':

            # 시작 시간
            start_dt = datetime.today()

            print(f"해외선물 {self.base_min_unit}분차트 조회 시작!")

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

                self.ohlcv = pd.concat([ohlcv, self.ohlcv], ignore_index=True)

            # 종료 시간
            end_dt = datetime.today()

            # 실행 시간
            delta = (end_dt - start_dt).total_seconds()

            print(f"해외선물 {self.base_min_unit}분차트 조회 끝!")
            print(f"({delta}초 = {end_dt} - {start_dt})")

        elif sRQName == '미결제잔고내역조회':

            # 싱글데이타 index = 0

            s_qty = int(self._comm_get_data(sTrCode, sRQName, 0, "매도수량"))
            l_qty = int(self._comm_get_data(sTrCode, sRQName, 0, "매수수량"))
            pl = float(self._comm_get_data(sTrCode, sRQName, 0, "총평가금액")) / 100
            self.position.c_pl = float(self._comm_get_data(sTrCode, sRQName, 0, "실현수익금액")) / 100

            # 전체 미결제잔고 내역 출력
            print(f"[미결제잔고내역-전체] 매도수량: {s_qty}, 매수수량: {l_qty}, 평가손익(원): {pl}, 실현손익(원): {self.position.c_pl}")

            # 청산시 포지션 초기화
            if s_qty + l_qty == 0:
                self.position.code = ''
                self.position.gb = 0
                self.position.qty = 0
                self.position.d_qty = 0
                self.position.a_price = 0
                self.position.c_price = 0
                self.position.pl = 0
                self.position.pl_KRW = 0
                self.position.r_pl = 0
                self.position.r_pl_KRW = 0
                self.position.pl_pct = 0

                self.position.commission = 1

                print(f"[미결제잔고내역-청산] 포지션 초기화")

            else:

                data_cnt = self._get_repeat_cnt(sTrCode, sRQName)

                for i in range(0, data_cnt):
                    self.position.code = self._comm_get_data(sTrCode, sRQName, i, "종목코드")
                    #gb = '매수' if self._comm_get_data(sTrCode, sRQName, i, "매도수구분") == '2' else '매도'
                    self.position.gb = int(self._comm_get_data(sTrCode, sRQName, i, "매도수구분"))
                    self.position.qty = int(self._comm_get_data(sTrCode, sRQName, i, "수량"))
                    self.position.d_qty = int(self._comm_get_data(sTrCode, sRQName, i, "청산가능"))
                    self.position.a_price = float(self._comm_get_data(sTrCode, sRQName, i, "평균단가"))
                    self.position.c_price = float(self._comm_get_data(sTrCode, sRQName, i, "현재가격"))
                    self.position.pl = float(self._comm_get_data(sTrCode, sRQName, i, "평가손익")) / 100
                    self.position.commission = float(self._comm_get_data(sTrCode, sRQName, i, "수수료"))

                    print(f"[미결제잔고내역-{self.position.code}] 매도수구분: {self.position.gb}, "
                          f"수량: {self.position.qty}, 청산가능: {self.position.d_qty}, "
                          f"평단가: {self.position.a_price}, 현재가: {self.position.c_price}, 평가손익($): {self.position.pl}, "
                          f"수수료: {self.position.qty}")


    def on_receive_msg(self, screen_number, rq_name, tr_code, msg):

        print('== on_receive_msg ==')
        print(f'{rq_name}, {msg}')

    def get_chejan_data(self, fid):
        ret = self.dynamicCall("GetChejanData(int)", fid)
        return ret

    """ 
    FID : 913(주문상태)
    - 1: 접수 (신규주문시 실시간 주문내역에서 1로 내려옴)
    - 2: 확인 (신규주문을 정정/취소시 실시간 체결내역에서 2로 내려옴.)
    - 3: 체결 (신규주문이 체결되면 실시간 체결내역에서 3으로 내려옴.)
    """

    def on_receive_chejan_data(self, sGubun, nItemCnt, sFidList):
        #pass
        # self.get_current_position()
        print(f"== on_receive_chejan_data (sGubun: {sGubun}) ==")

        if int(sGubun) == 0:  # 주문내역
            o_state = self.get_chejan_data(913) # 주문상태
            o_gb = '매수' if self.get_chejan_data(907) == '2' else '매도'  # 매도수구분
            o_qty = self.get_chejan_data(900)  # 주문수량
            self.o_price = float(self.get_chejan_data(901))  # 주문가
            self.o_dt = datetime.strptime(self.get_chejan_data(908),'%Y%m%d%H%M%S%f')  # 주문시간

            print(f"[주문내역] 주문시간: {self.o_dt}, 주문상태: {o_state}, 구분: {o_gb}, 주문가격: {self.o_price}, 주문수량: {o_qty} ")

            pass

        elif int(sGubun) == 1:  # 체결내역

            t_state = self.get_chejan_data(913)  # 주문상태

            if t_state == '2':

                print(f"[체결내역] 주문 정정/취소 확인")

                pass

            elif t_state == '3':

                t_gb = '매수' if self.get_chejan_data(907) == '2' else '매도'  # 매도수구분
                t_qty = self.get_chejan_data(911)  # 체결수량
                t_r_qty = self.get_chejan_data(902)  # 주문 잔량, 미체결수량, r = remaining
                self.t_price = float(self.get_chejan_data(910))  # 체결가격

                self.exRate = float(self.get_chejan_data(50718))  # 원화환율
                self.commission = float(self.get_chejan_data(50717))  # 종목수수료, 935 체결 수수료는 미지원 (키움 게시판)


                self.t_dt = datetime.strptime(self.get_chejan_data(908),'%Y%m%d%H%M%S%f')  # 체결수신시간

                # 주문-체결 시간 델타
                delta = (self.t_dt - self.o_dt).total_seconds()

                # 주문-체결 가격 델타
                delta2 = (self.o_price - self.t_price) if t_gb == '매수' else (self.t_price - self.o_price)

                # 잔고
                # 청산가능 수량
                t_c_qty = int(self.get_chejan_data(50711))  # 미결제청산가능수량, c = close


                print(f"[체결내역] 체결시간: {self.t_dt}({delta}초), 체결가: {self.t_price:.2f}({delta2:.2f}), 주문상태: {t_state}, 구분: {t_gb}, 체결량: {t_qty}, 미체결: {t_r_qty},  "
                      f" 청산가능: {t_c_qty}")
                print(f"[체결내역-참고] 원화환율: {self.exRate}, 종목수수료: {self.commission}")

            # 미결제잔고내역조회 (opw30003)
            # 체결후 포지션(잔고) 업데이트
            self.req_opw30003()

            pass

        elif int(sGubun) == 3:  # 마진콜
            pass

    def on_receive_real_data(self, sCode, sRealType, sRealData):

        if sRealType == '해외선물시세':
            # print(sRealData)

            n_time = self._get_comm_real_data(sCode, 20)  # 체결 시간
            n_date = self._get_comm_real_data(sCode, 22)  # 체결 일자
            c_dt = pd.to_datetime(n_date + n_time)

            c_price = abs(float(self._get_comm_real_data(sCode, 10)))  # 현재가(체결가)
            c_volume = abs(int(self._get_comm_real_data(sCode, 15)))  # 거래량 (+ 매수체결, - 매도체결)

            # 틱 카운트 +1 증가
            # 1(시가),2,3,4,0(종가)
            self.t_cnt += 1

            gb = self.t_cnt % self.base_tick_unit

            # 1: 새틱차트 생성
            # 새틱차트 시작, 새틱차트 생성
            if gb == 1:

                # print(f"틱 카운트: {self.t_cnt}, 구분: {gb}, 새틱차트 생성, 시작시간: {c_dt}, 시가(현재가): {c_price:.2f}, 시작수량: {c_volume} ")

                ohlcv = pd.DataFrame(
                    {'date_time': c_dt, 'Open': c_price, 'High': 0, 'Low': 100000,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.ohlcv = pd.concat([self.ohlcv, ohlcv], ignore_index=True)

                # 마지막차트 출력
                print(f"[{self.base_tick_unit}틱-{self.ohlcv.index[-2]}] 체결시간: {self.ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.ohlcv.Open.iloc[-2]:.2f}, 고가: {self.ohlcv.High.iloc[-2]:.2f}, 저가: {self.ohlcv.Low.iloc[-2]:.2f}, 종가: {self.ohlcv.Close.iloc[-2]:.2f}, 거래량: {self.ohlcv.Volume.iloc[-2]}")

                # 자동 매매 실행
                if self._system_running:
                    self._run_system()

            # 2,3,4,0: 기존차트에서 틱업데이트
            else:

                # 고가와 저가 업데이트
                if self.ohlcv.High.iloc[-1] < c_price:
                    self.ohlcv.High.iloc[-1] = c_price
                if self.ohlcv.Low.iloc[-1] > c_price:
                    self.ohlcv.Low.iloc[-1] = c_price

                # 종가와 거래량 업데이트
                self.ohlcv.Close.iloc[-1] = c_price
                self.ohlcv.Volume.iloc[-1] += c_volume

                # print(f"틱 카운트: {self.t_cnt}, 구분: {gb}, 기존틱차트 업데이트, 수량: {self.ohlcv.Volume.iloc[-1]} ")

            # Position 실시간 업데이트
            self.position.update(c_price)

            # Main Window 업데이트
            # self.mw.label_7.setText(str(c_price))
            self.mw.lineEdit.setText(str(c_price))
            # 실시간 손익 업데이트
            #self.mw.lineEdit_6.setText(str(self.position.pl))



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
        self.set_input_value("계좌번호", account_num)
        self.set_input_value("비밀번호", password)
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("종목코드", code)
        self.set_input_value("매도수구분", ls_gb)  # 1: 매도, 2: 매수
        self.set_input_value("해외주문유형", order_type)  # 1: 시장가, 2: 지정가, ...
        self.set_input_value("주문수량", str(qty))
        self.set_input_value("주문표시가격", str(price))
        self.set_input_value("STOP구분", str(stop_gb))
        self.set_input_value("STOP표시가격", str(stop_price))
        self.set_input_value("LIMIT구분", str(limit_gb))
        self.set_input_value("LIMIT표시가격", str(limit_price))
        self.set_input_value("해외주문조건구분", "0")  # 0: 당일, 6: GTD
        self.set_input_value("주문조건종료일자", "")
        self.set_input_value("통신주문구분", "AP")

        ret = self.comm_rq_data("해외파생신규주문2", "opw10008", "", self.get_screen_number())       #self.order_event_loop.exec_()

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

    def req_opw30003(self):
        #QMessageBox.about(self, "message", "req_opw30003")

        # 선물틱차트조회
        self.set_input_value("계좌번호", self.future_accno) #7018311472
        self.set_input_value("비밀번호", "") # 미입력시 -301 에러
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("통화코드", "KRW") #통화코드 = USD, KRW, JPY, HKD, CNY
        ret = self.comm_rq_data("미결제잔고내역조회","opw30003","", self.get_screen_number())

        """
        #print(f"ret = {ret}")
        # 정상처리가 안되면 메세지 박스에 에러코드 출력하고 멈춰있기
        if ret != 0:
            #QMessageBox.about(self, "message", str(ret))
            QMessageBox.about(self, "message", "비밀번호를 입력하세요")
            
        """



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
        #QMessageBox.about(self, "message", "position close")
        self.mw.label_7.setText("position close")

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        hts = Kiwoom_NQ100()

        #QMessageBox.about(hts, "message", "비번입력")

        window = Window(hts)
        window.show()

        #window.statusBar().showMessage(hts.comm_status)

        sys.exit( app.exec_() )
    except Exception as e:
        print(e)

