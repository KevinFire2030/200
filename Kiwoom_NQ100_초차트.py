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
        # 미체결 주문 일괄 취소
        self.pushButton_16.clicked.connect(self.hts.order.cancle)

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

        # 주문-체결 Delta
        self.o_price = 0 # order price, 주문가
        self.t_price = 0 # trade price, 체결가
        self.d_price = 0 # 체결시 주문-체결 가격 Delta (매수시 = self.o_price - self.t_price, 매도시 = self.t_price - self.o_price )

        self.o_eN = 0  # order entry N, 주문시 N
        self.t_eN = 0  # trade entry N, 체결시 N
        self.d_eN = 0  # 체결시 주문-체결 eN Delta (= self.t_eN - self.o_eN)

        self.o_sp = 0  # order stop price, 주문시 stop price (매수시 = self.o_price - self.o_eN * 2, 매도시 = self.o_price + self.o_eN * 2)
        self.t_sp = 0  # trade stop price, 체결시 stop price (매수시 = self.t_price - self.t_eN * 2, 매도시 = self.t_price + self.t_eN * 2)
        self.d_sp = 0  # 체결시 주문-체결 sp Delta (= self.t_sp - self.o_sp)

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
            pl = round(p_delta * self.qty * self.get_point_value(self.code), 1)
            # 평가(청산) 손익 (원)
            pl_KRW = round(pl * self.get_exRate(), 0)
            # 실손익 ($)
            r_pl = round(pl - self.get_commission() * self.qty, 1)
            # 모투 수수료 적용 for 검증
            #r_pl = pl - self.commission * self.qty
            # 실손익 (원)
            r_pl_KRW = round(r_pl * self.get_exRate(), 0)
            # 수익률
            pl_pct = round(p_delta / self.a_price * 100, 2)

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

        self.__broker.order.cancle()

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


class Order:
    def __init__(self, broker: 'Kiwoom_NQ100'):
        self.__broker = broker


        self.pending = pd.DataFrame(columns=['주문번호', '종목코드', '주문유형', '매도수구분', '주문수량', '체결수량', '미체결수량', '주문표시가격', '주문가격', '조건표시가격', '상태구분', '통화코드', '주문시각', '원주문번호'])

    def cancle(self):

        # 된다! 하면된다! 할수 있다! Just Do It Now!!

        # 미체결 주문 확인
        self.__broker.req_opw30001()

        if len(self.pending) >= 1:


            for i in range(0,len(self.pending)):

                gb = 3 if self.pending.loc[i,"매도수구분"] == 1 else 4 # 주문 유형, 3: 매도 취소, 4:매수 취소
                code = self.pending.loc[i,"종목코드"]
                qty = self.pending.loc[i,"주문수량"]
                o_num = str(self.pending.loc[i, "주문번호"])

                # 미체결주문 취소
                self.__broker.send_order("미체결주문 취소", self.__broker.get_screen_number(), self.__broker.future_accno, \
                                         gb, code, qty, '', '', '', o_num)




class Kiwoom_NQ100(QAxWidget):
    def __init__(self):
        super().__init__()
        self._create_kiwoom_instance()
        self._set_signal_slots()

        # 시간 측정
        self.s_dt = 0
        self.e_dt = 0


        # 이벤트 루프
        self.tr_event_loop = QEventLoop()
        self.tr_opw30001_event_loop = QEventLoop()
        self.login_event_loop = QEventLoop()

        self.comm_connect()

        # 계좌정보
        account_numbers = self.get_login_info("ACCNO")
        self.future_accno = account_numbers.split(';')[0]  # 7011576372

        # 포지션
        self.position = Position(self)
        self.exRate = 1
        self.commission = 1

        # 미체결주문
        self.order = Order(self)


        # 실시간 틱차트 (t : tick, c = current)
        self.ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N'])

        # 실시간 초차트 (t : tick, c = current)
        self.s_ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N'])

        self.base_min_unit = 1
        self.base_tick_unit = 120
        self.base_sec_unit = 1
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
        self.unit_limit = 10

        # 체잔 주문/체결 시간
        self.o_dt = 0
        self.t_dt = 0
        self.o_price = 0
        self.t_price = 0

        # 미결제잔고내역조회 (opw30003)
        # 프로그램 시작전에 미결제 잔고가 있는지 확인
        # 잔고가 있으면 포지션 업데이트
        # 비밀번호 선 입력 문제 해결 필요
        # self.req_opw30003()



        # 선물분차트조회
        self.set_input_value("종목코드", self.code_symbol)
        self.set_input_value("시간단위", self.base_min_unit)
        self.comm_rq_data("해외선물분차트조회", "opc10002", '', self.get_screen_number())

        # 선물초차트조회
        # 키움해선 게시판 문의 중


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

                self.position.o_price = 0
                self.position.o_sp = 0
                self.position.o_eN = 0

                self.position.t_price = 0
                self.position.t_sp = 0
                self.position.t_eN = 0



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


            self.tr_event_loop.exit()

        elif sRQName == "미체결내역조회":

            data_cnt = self._get_repeat_cnt(sTrCode, sRQName)

            print(f"[미체결내역조회] 미체결 주문 : {data_cnt}건")

            if data_cnt == 0:

                # 초기화
                self.order.pending = pd.DataFrame()

                #print(f"미체결 주문이 없습니다.")

            else:

                # 초기화
                self.order.pending = pd.DataFrame(columns=['주문번호', '종목코드', '주문유형', '매도수구분', '주문수량', '체결수량', '미체결수량', '주문표시가격', '주문가격', '조건표시가격', '상태구분', '통화코드', '주문시각', '원주문번호'])

                for i in range(0, data_cnt):

                    num = int(self._comm_get_data(sTrCode, sRQName, i, "주문번호")) # '000000607019560', 앞에 0을 없애기 위해 int() 형변환
                    code = self._comm_get_data(sTrCode, sRQName, i, "종목코드")
                    type = int(self._comm_get_data(sTrCode, sRQName, i, "주문유형")) # 해외주문유형 = 1:시장가, 2:지정가, 3:STOP, 4:StopLimit, 5:OCO, 6:IF DONE
                    gb = int(self._comm_get_data(sTrCode, sRQName, i, "매도수구분")) # 1: 매도, 2: 매수
                    o_qty = int(self._comm_get_data(sTrCode, sRQName, i, "주문수량")) # order qty
                    d_qty = int(self._comm_get_data(sTrCode, sRQName, i, "체결수량")) # done qty, 체결수량
                    p_qty = int(self._comm_get_data(sTrCode, sRQName, i, "미체결수량")) # pending qty, 미체결수량
                    o_dprice = self._comm_get_data(sTrCode, sRQName, i, "주문표시가격")  # order_display_price, 주문표시가격
                    o_dprice = float(o_dprice) if o_dprice != '' else 0
                    o_price = self._comm_get_data(sTrCode, sRQName, i, "주문가격")  # order_price, 주문가격, 시장가
                    o_price = float(o_price) if o_price != '' else 0
                    c_dprice = self._comm_get_data(sTrCode, sRQName, i, "조건표시가격")  # condition_display_price, 조건표시가격
                    c_dprice = float(c_dprice) if c_dprice != '' else 0
                    state = int(self._comm_get_data(sTrCode, sRQName, i, "상태구분"))  # 상태구분, 1: 접수, 2: 확인, 3. 체결
                    c_code = self._comm_get_data(sTrCode, sRQName, i, "통화코드")  # currency_code
                    o_dt = self._comm_get_data(sTrCode, sRQName, i, "주문시각")  # order_datatime, 주문시각, '06/07 15:11:03'
                    o_num = int(self._comm_get_data(sTrCode, sRQName, i, "원주문번호")) # origianl order number

                    p_order = pd.DataFrame(
                        {'주문번호': num, '종목코드': code, '주문유형': type, '매도수구분': gb, '주문수량': o_qty, \
                         '체결수량': d_qty, '미체결수량': p_qty, '주문표시가격': o_dprice, '주문가격': o_price,
                         '조건표시가격': c_dprice, '상태구분': state, '통화코드': c_code, '주문시각': o_dt, '원주문번호': o_num}, index=[0])

                    self.order.pending = pd.concat([p_order, self.order.pending], ignore_index=True)


            self.tr_opw30001_event_loop.exit()



            pass






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

                ######## 주문-체결 오차

                # 주문-체결 시간 델타
                delta = (self.t_dt - self.o_dt).total_seconds()

                # 주문-체결 가격 델타
                delta2 = (self.o_price - self.t_price) if t_gb == '매수' else (self.t_price - self.o_price)

                # 잔고
                # 청산가능 수량
                t_c_qty = int(self.get_chejan_data(50711))  # 미결제청산가능수량, c = close

                ######## 주문-체결 오차 추가 구현
                self.position.t_price = self.t_price
                self.position.t_eN = self.ohlcv.N.iloc[-1]
                self.position.t_sp = (self.position.t_price - 2 * self.position.t_eN) if t_gb == '매수' else (self.position.t_price + 2 * self.position.t_eN)

                self.position.d_price = (self.position.o_price - self.position.t_price) if t_gb == '매수' else (self.position.t_price - self.position.o_price)
                self.position.d_eN = self.position.t_eN - self.position.o_eN
                self.position.d_sp = self.position.t_sp - self.position.o_sp

                print(f"[체결내역] 체결시간: {self.t_dt}({delta}초), 체결가: {self.t_price:.2f}({delta2:.2f}), 주문상태: {t_state}, 구분: {t_gb}, 체결량: {t_qty}, 미체결: {t_r_qty},  "
                      f" 청산가능: {t_c_qty}")
                print(f"[체결내역-참고] 원화환율: {self.exRate}, 종목수수료: {self.commission}")

                print(f"[주문체결 델타] 시간: {delta}, 가격: {self.position.d_price}, eN: {self.position.d_eN}, sp: {self.position.d_sp}")


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
            n_dt = pd.to_datetime(n_date + n_time)

            dt = self.ohlcv.date_time.iloc[-1]
            delta = n_dt.minute - dt.minute



            c_price = abs(float(self._get_comm_real_data(sCode, 10)))  # 현재가(체결가)
            c_volume = abs(int(self._get_comm_real_data(sCode, 15)))  # 거래량 (+ 매수체결, - 매도체결)

            ########## 1초 차트 ################

            # 초차트 조회 TR이 없어 임시 초기화
            if len(self.s_ohlcv) == 0:

                base_second = n_dt.second - (n_dt.second % self.base_sec_unit)

                if base_second == 0:
                    base_second = "00"
                elif base_second < 10:
                    base_second = "0" + str(base_second)



                new_dt = pd.to_datetime(n_date + n_time[0:4] + str(base_second))

                s_ohlcv = pd.DataFrame(
                    {'date_time': new_dt, 'Open': c_price, 'High': c_price, 'Low': c_price,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.s_ohlcv = pd.concat([self.s_ohlcv, s_ohlcv], ignore_index=True)

            s_dt = self.s_ohlcv.date_time.iloc[-1]

            #s_delta = (n_dt.second // self.base_sec_unit)  - (s_dt.second // self.base_sec_unit)
            s_delta = n_dt.second - s_dt.second

            print(f"s_delta: {s_delta} = {n_dt.second} - {s_dt.second}")

            """
            if s_delta > self.base_sec_unit :


                print(f"s_delta > self.base_sec_unit 새로운 new_dt 생성")

                base_second = n_dt.second - (n_dt.second % self.base_sec_unit)

                if base_second == 0:
                    base_second = "00"
                elif base_second < 10:
                    base_second = "0" + str(base_second)

                new_dt = pd.to_datetime(n_date + n_time[0:4] + str(base_second))

                s_ohlcv = pd.DataFrame(
                    {'date_time': new_dt, 'Open': c_price, 'High': c_price, 'Low': c_price,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.s_ohlcv = pd.concat([self.s_ohlcv, s_ohlcv], ignore_index=True)

                # [-2] 출력
                print(f"[{self.base_sec_unit}초-{self.s_ohlcv.index[-2]}] 체결시간: {self.s_ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.s_ohlcv.Open.iloc[-2]:.2f}, 고가: {self.s_ohlcv.High.iloc[-2]:.2f}, 저가: {self.s_ohlcv.Low.iloc[-2]:.2f}, 종가: {self.s_ohlcv.Close.iloc[-2]:.2f}, 거래량: {self.s_ohlcv.Volume.iloc[-2]}")

                # s_dt와 s_delta 다시 계산
                s_dt = self.s_ohlcv.date_time.iloc[-1]

                # s_delta = (n_dt.second // self.base_sec_unit)  - (s_dt.second // self.base_sec_unit)
                s_delta = n_dt.second - s_dt.second

            print(f"s_delta: {s_delta} = {n_dt.second} - {s_dt.second}")
            
            
            """


            if s_delta < self.base_sec_unit and s_delta >= 0 :

                # 고가와 저가 업데이트

                #print(f"고가와 저가 업데이트")

                if self.s_ohlcv.High.iloc[-1] < c_price:
                    self.s_ohlcv.High.iloc[-1] = c_price
                if self.s_ohlcv.Low.iloc[-1] > c_price:
                    self.s_ohlcv.Low.iloc[-1] = c_price

                # 종가와 거래량 업데이트
                self.s_ohlcv.Close.iloc[-1] = c_price
                self.s_ohlcv.Volume.iloc[-1] += c_volume

            elif s_delta  >= self.base_sec_unit or s_delta < 0  : # 매분 정초

                # 시가와 시간 업데이트

                #print(f"시가와 시간 업데이트")

                s_ohlcv = pd.DataFrame(
                    {'date_time': n_dt, 'Open': c_price, 'High': c_price, 'Low': c_price,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.s_ohlcv = pd.concat([self.s_ohlcv, s_ohlcv], ignore_index=True)

                #

                if s_delta > self.base_sec_unit or s_delta < 0:

                    base_second = n_dt.second - (n_dt.second % self.base_sec_unit)

                    if base_second == 0:
                        base_second = "00"
                    elif base_second < 10:
                        base_second = "0" + str(base_second)

                    new_dt = pd.to_datetime(n_date + n_time[0:4] + str(base_second))

                    self.s_ohlcv.date_time.iloc[-1] = new_dt


                print(f"[{self.base_sec_unit}초-{self.s_ohlcv.index[-2]}] 체결시간: {self.s_ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.s_ohlcv.Open.iloc[-2]:.2f}, 고가: {self.s_ohlcv.High.iloc[-2]:.2f}, 저가: {self.s_ohlcv.Low.iloc[-2]:.2f}, 종가: {self.s_ohlcv.Close.iloc[-2]:.2f}, 거래량: {self.s_ohlcv.Volume.iloc[-2]}")

                if self._system_running:
                    self._run_system()


            #################################


            if delta < self.base_min_unit and delta >=0 :

                # 고가와 저가 업데이트
                if self.ohlcv.High.iloc[-1] < c_price:
                    self.ohlcv.High.iloc[-1] = c_price
                if self.ohlcv.Low.iloc[-1] > c_price:
                    self.ohlcv.Low.iloc[-1] = c_price

                # 종가와 거래량 업데이트
                self.ohlcv.Close.iloc[-1] = c_price
                self.ohlcv.Volume.iloc[-1] += c_volume

            elif delta == self.base_min_unit or delta < 0: # 매시 정시

                # 시가와 시간 업데이트
                new_dt = pd.to_datetime(n_date + n_time[0:4] + '00')

                ohlcv = pd.DataFrame(
                    {'date_time': new_dt, 'Open': c_price, 'High': 0, 'Low': 100000,
                     'Close': c_price, 'Volume': c_volume}, index=[0])
                self.ohlcv = pd.concat([self.ohlcv, ohlcv], ignore_index=True)

                print(f"[{self.base_min_unit}분-{self.ohlcv.index[-2]}] 체결시간: {self.ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.ohlcv.Open.iloc[-2]:.2f}, 고가: {self.ohlcv.High.iloc[-2]:.2f}, 저가: {self.ohlcv.Low.iloc[-2]:.2f}, 종가: {self.ohlcv.Close.iloc[-2]:.2f}, 거래량: {self.ohlcv.Volume.iloc[-2]}")


                """
                # 자동 매매
                if self._system_running:
                    self._run_system()
                """



            # Position 실시간 업데이트
            self.position.update(c_price)

            # Main Window 업데이트
            # self.mw.label_7.setText(str(c_price))
            self.mw.lineEdit.setText(str(c_price))
            # 실시간 손익 업데이트
            #self.mw.lineEdit_6.setText(str(self.position.pl))



    def _run_system(self):

        # Breakouts과 N계산
        df = self.s_ohlcv[-30:]
        df = self._calc_breakouts(df)
        df = self._calc_N(df)

        # ohlcv에 시스템 1의 Breakouts 추가
        self.s_ohlcv.S1_EL.iloc[-2] = df.S1_EL.iloc[-2]
        self.s_ohlcv.S1_ES.iloc[-2] = df.S1_ES.iloc[-2]
        self.s_ohlcv.S1_ExL.iloc[-2] = df.S1_ExL.iloc[-2]
        self.s_ohlcv.S1_ExS.iloc[-2] = df.S1_ExS.iloc[-2]

        # ohlcv에 N 추가
        self.s_ohlcv.N.iloc[-2] = df.N.iloc[-2]

        # 현재가격
        price = self.s_ohlcv.Close.iloc[-2]

        # 시스템 1
        S1_EL = self.s_ohlcv.S1_EL.iloc[-2]
        S1_ES = self.s_ohlcv.S1_ES.iloc[-2]

        S1_ExL = self.s_ohlcv.S1_ExL.iloc[-2]
        S1_ExS = self.s_ohlcv.S1_ExS.iloc[-2]

        N = self.s_ohlcv.N.iloc[-2]

        if self.position.qty == 0:

            if price == S1_EL:


                self.position.o_price = price
                self.position.o_eN = N
                self.position.o_sp = price - 2 * N


                # 지정가 매수 주문

                self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'),
                                 self.get_order_type('시장가'), 1, price, \
                                 '0', '', '0', '')

                print(f"[롱포지션 진입] units_size = 1")


            elif price == S1_ES:
                # 지정가 매도 주문

                self.position.o_price = price
                self.position.o_eN = N
                self.position.o_sp = price + 2 * N

                # 지정가 매수 주문

                self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'),
                                 self.get_order_type('시장가'), 1, price, \
                                 '0', '', '0', '')

                print(f"[숏포지션 진입] units_size = 1")

        # 포지션이 있으면
        else:



            if self.position.gb == 2:  # 롱 (매수)

                print(
                    f"[현재 포지션: 롱] 현재가: {price}, 평단가: {self.position.a_price}, 마지막 진입가: {self.position.o_price}, "
                    f"손절가: {self.position.o_price - 2 * self.position.o_eN}, 피라미딩: {self.position.o_price + self.position.o_eN}, eN:{self.position.o_eN} ")

                # Check to exit existing long position
                if price == S1_ExL:
                    print(f"[롱포지션 청산]")
                    self.position.close()

                elif price <= self.position.o_sp:
                    print(f"[롱포지션 손절]")
                    self.position.close()

                # Check to pyramid existing position
                elif self.position.qty <= self.unit_limit:


                    if price >= self.position.o_price + self.position.o_eN:

                        print(
                            f"[롱포지션 피라미딩] 현재가 {price} >= 롱피라미딩 {self.position.o_price + self.position.o_eN}, ep: {self.position.o_price}, eN: {self.position.o_eN} ")

                        self.position.o_price = price
                        self.position.o_eN = N
                        self.position.o_sp = price - 2 * N

                        # 지정가 매수 주문

                        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매수'),
                                         self.get_order_type('시장가'), 1, price, \
                                         '0', '', '0', '')



            if self.position.gb == 1:  # 숏 (매도)

                print(
                    f"[현재 포지션: 숏] 현재가: {price}, 평단가: {self.position.a_price}, 마지막 진입가: {self.position.o_price}, "
                    f"손절가: {self.position.o_price + 2 * self.position.o_eN}, 피라미딩: {self.position.o_price - self.position.o_eN}, eN:{self.position.o_eN} ")

                # Check to exit existing short position
                if price == S1_ExS:
                    print(f"[숏포지션 청산]")
                    self.position.close()

                elif price >= self.position.o_sp:
                    print(f"[숏포지션 손절]")
                    self.position.close()

                # Check to pyramid existing position
                elif self.position.qty <= self.unit_limit:

                    if price <= self.position.o_price - self.position.o_eN:

                        print(
                            f"[숏포지션 피라미딩] 현재가 {price} <= 숏피라미딩 {self.position.o_price - self.position.o_eN}, ep: {self.position.o_price}, eN: {self.position.o_eN} ")

                        self.position.o_price = price
                        self.position.o_eN = N
                        self.position.o_sp = price + 2 * N

                        # 지정가 매도 주문

                        self.send_order2(self.future_accno, "", self.code_symbol, self.get_order_gb('매도'),
                                         self.get_order_type('시장가'), 1, price, \
                                         '0', '', '0', '')



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

    def send_order(self, sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, sPrice, sStop, sHogaGb, sOrgOrderNo):
        if not (isinstance(sRQName, str)
                and isinstance(sScreenNo, str)
                and isinstance(sAccNo, str)
                and isinstance(nOrderType, int)
                and isinstance(sCode, str)
                and isinstance(nQty, int)
                and isinstance(sPrice, str)
                and isinstance(sStop, str)
                and isinstance(sHogaGb, str)
                and isinstance(sOrgOrderNo, str)):
            print("Error : ParameterTypeError by SendOrder")

        error_code = self.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, QString, QString, QString, QString)",
            [sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, sPrice, sStop, sHogaGb, sOrgOrderNo])
        print('error_code: ' + str(error_code))
        return error_code

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
        elif type == '매수취소':
            return '3'
        elif type == '매도취소':
            return '4'
        elif type == '매수정정':
            return '5'
        elif type == '매도정정':
            return '6'

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


############# 테스트 버튼 action, TR 요청 ################

    def req_opw30001(self):
        #QMessageBox.about(self, "message", "req_opw30001")

        # 미결체결내역조회
        self.set_input_value("계좌번호", self.future_accno)  # 7018311472
        self.set_input_value("비밀번호", "")  # 미입력시 -301 에러
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("종목코드", "") #종목코드 = 전체(space), 전문 조회할 종목코드
        self.set_input_value("통화코드", "")  #통화코드 = 전체(space), USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD
        self.set_input_value("매도수구분", "") #매도수구분 = 전체(space), 1:매도, 2:매수
        ret = self.comm_rq_data("미체결내역조회", "opw30001", "", self.get_screen_number())

        # 시작 시간
        self.s_dt = datetime.today()

        self.tr_opw30001_event_loop.exec_()

        # 종료 시간
        self.e_dt = datetime.today()

        # 실행 시간
        delta = (self.e_dt - self.s_dt).total_seconds()

        #(opw30001 실행 시간 0.013012초 (= 2024-06-07 13:46:39.389896 - 2024-06-07 13:46:39.376884)
        print(f"(opw30001 실행 시간 {delta}초 (= {self.e_dt} - {self.s_dt})")



    def req_opw30003(self):
        #QMessageBox.about(self, "message", "req_opw30003")

        # 미결제잔고내역조회
        self.set_input_value("계좌번호", self.future_accno) #7018311472
        self.set_input_value("비밀번호", "") # 미입력시 -301 에러
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("통화코드", "KRW") #통화코드 = USD, KRW, JPY, HKD, CNY
        ret = self.comm_rq_data("미결제잔고내역조회","opw30003","", self.get_screen_number())

        # 시작 시간
        self.s_dt = datetime.today()

        self.tr_event_loop.exec_()

        # 종료 시간
        self.e_dt = datetime.today()

        # 실행 시간
        delta = (self.e_dt - self.s_dt).total_seconds()


        # (opw30008 실행 시간 0.014014초 (= 2024-06-06 16:20:49.414464 - 2024-06-06 16:20:49.400450)
        print(f"(opw30008 실행 시간 {delta}초 (= {self.e_dt} - {self.s_dt})")

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

