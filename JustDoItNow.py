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

        # 계좌번호
        self.accno = ''

        # 이벤트 루프
        self.login_event_loop = QEventLoop()
        self.opw30003_event_loop = QEventLoop()
        self.chejan_event_loop = True


        # 스크린 번호
        self.screen_number = 1000

        # 종목코드
        self.ticker = ticker  # MNQZ23

        # 실시간 차트 시간단위
        self.tick_unit = tick_unit
        self.t_cnt = 0


        # 차트
        self.t_ohlcv = pd.DataFrame(
            columns=['date_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'S1_EL', 'S1_ES', 'S1_ExL', 'S1_ExS', 'N', 'S', 'ma5', 'ma20', 'ma40'])

        # 자동 매매
        self.system_running = False

        # 미결재잔고
        self.opw30003 = pd.Series({'종목코드': '',
                                   '매도수구분': 0,
                                   '수량': 0,
                                   '청산가능': 0,
                                   '평균단가': 0,
                                   '현재가격': 0,
                                   '평가손익': 0,
                                   '약정금액': 0,
                                   '평가금액': 0,
                                   '수익율': 0,
                                   '수수료': 0,
                                   '통화코드': ''})

        # 체잔
        self.chejan = pd.Series({'종목코드': '',
                                 '매도수구분': 0,
                                 '체결가격': 0,
                                 '평균가격': 0,  # 사용자 추가
                                 '손절가격': 0, # 사용자 추가
                                 '피라미딩가격': 0, # 사용자 추가
                                 '신규수량': 0,
                                 '체결수량': 0,
                                 '청산수량': 0,
                                 '미결제매도수구분': 0,
                                 '미결제청산가능수량': 0})

        # 체결가
        self.trade = pd.DataFrame(columns=['체결가격', '체결수량'])

        # 터틀 트레이딩
        """
        self.atr_periods = 20
        self.sys1_entry = 20
        self.sys1_exit = 10
        self.unit_limit = 10
        """

        self.turtle = pd.Series({'atr_periods': 20,
                                 'sys1_entry': 20,
                                 'sys1_exit': 10,
                                 'size_limit': 10})


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

    def req_opw30003(self):
        # QMessageBox.about(self, "message", "req_opw30003")

        # 미결제잔고내역조회
        self.set_input_value("계좌번호", self.accno)  # 7018311472
        self.set_input_value("비밀번호", "")  # 미입력시 -301 에러
        self.set_input_value("비밀번호입력매체", "00")
        self.set_input_value("통화코드", "KRW")  # 통화코드 = USD, KRW, JPY, HKD, CNY
        ret = self.comm_rq_data("미결제잔고내역조회", "opw30003", "", self.get_screen_number())

        # 시작 시간
        self.s_dt = datetime.today()

        self.opw30003_event_loop.exec_()

        # 종료 시간
        self.e_dt = datetime.today()

        # 실행 시간
        delta = (self.e_dt - self.s_dt).total_seconds()

        # (opw30008 실행 시간 0.014014초 (= 2024-06-06 16:20:49.414464 - 2024-06-06 16:20:49.400450)
        print(f"(opw30003 실행 시간 {delta}초 (= {self.e_dt} - {self.s_dt})")

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



        elif sRQName == '미결제잔고내역조회':

            # 싱글데이타 index = 0
            """
            # 미결재잔고
            self.opw30003 = pd.Series({'종목코드': '',
                                       '매도수구분': 0,
                                       '수량': 0,
                                       '청산가능': 0,
                                       '평균단가': 0,
                                       '현재가격': 0,
                                       '평가손익': 0,
                                       '약정금액': 0,
                                       '평가금액': 0,
                                       '수익율': 0,
                                       '수수료': 0,
                                       '통화코드': ''})
            """

            data_cnt = self._get_repeat_cnt(sTrCode, sRQName)

            for i in range(0, data_cnt):
                self.opw30003['종목코드'] = self._comm_get_data(sTrCode, sRQName, i, "종목코드")
                self.opw30003['매도수구분'] = int(self._comm_get_data(sTrCode, sRQName, i, "매도수구분"))
                self.opw30003['수량'] = int(self._comm_get_data(sTrCode, sRQName, i, "수량"))
                self.opw30003['청산가능'] = int(self._comm_get_data(sTrCode, sRQName, i, "청산가능"))
                self.opw30003['평균단가'] = float(self._comm_get_data(sTrCode, sRQName, i, "평균단가"))
                self.opw30003['현재가격'] = float(self._comm_get_data(sTrCode, sRQName, i, "현재가격"))
                self.opw30003['평가손익'] = float(self._comm_get_data(sTrCode, sRQName, i, "평가손익")) / 100
                self.opw30003['수수료'] = float(self._comm_get_data(sTrCode, sRQName, i, "수수료")) / 100
                self.opw30003['통화코드'] = self._comm_get_data(sTrCode, sRQName, i, "통화코드")

            self.opw30003_event_loop.exit()

    def get_chejan_data(self, fid):
        ret = self.dynamicCall("GetChejanData(int)", fid)
        return ret

    def on_receive_chejan_data(self, sGubun, nItemCnt, sFidList):

        if int(sGubun) == 0:  # 주문내역
            pass

        elif int(sGubun) == 1:  # 체결내역

            t_state = self.get_chejan_data(913)  # 주문상태

            if t_state == '2':

                #print(f"[체결내역] 주문 정정/취소 확인")

                pass

            elif t_state == '3':

                self.chejan['종목코드'] = self.get_chejan_data(90001)  # 미결제매도수구분
                self.chejan['매도수구분'] = int(self.get_chejan_data(907))  # 매도수구분
                self.chejan['체결가격'] = float(self.get_chejan_data(910))  # 체결가격
                self.chejan['체결수량'] = float(self.get_chejan_data(911))  # 체결수량
                self.chejan['신규수량'] = int(self.get_chejan_data(13327))  # 신규수량
                self.chejan['청산수량'] = int(self.get_chejan_data(13328))  # 청산수량

                self.chejan['미결제매도수구분'] = int(self.get_chejan_data(50710)) \
                                                if self.get_chejan_data(50710) != '' else 0 # 미결제매도수구분
                self.chejan['미결제청산가능수량'] = int(self.get_chejan_data(50711))  # 미결제청산가능수량

                # 평균가/손절가/피라미딩 세팅
                # 신규 수량일만
                if self.chejan['신규수량'] > 0:


                    # 체결가와 수량을 self.trade에 저장
                    # 일괄청산일때만 가능
                    trade = pd.DataFrame(
                        {'체결가격': self.chejan['체결가격'], '체결수량': self.chejan['체결수량']}, index=[0])
                    self.trade = pd.concat([self.trade, trade], ignore_index=True)

                    # 평단가 계산
                    v = (self.trade['체결가격'] * self.trade['체결수량']).sum()
                    q = self.trade['체결수량'].sum()
                    a = v / q


                    self.chejan['평균가격'] = round(a,2)

                    """
                    # 본전컷 구현
                    # 일단 보류
                    # 손절보다는 청산이 많네    
                    # [체잔] 미결제청산가능수량: 5, 신규수량: 1, 청산수량: 0, 체결가: 19578.25, 평단가: 19569.2 손절가: 19572.825, 피라미딩가: 19580.9625 
                    # 피라미딩 되면서 자동으로 손절가가 평단가보다 높아 지네  
                    # 손절가와 청산가 출력
                    # 손절가를 먼저 처리해야 하나
                    # 항상 청산이 손절보다 먼저네, 심지어 포지션 수량이 1개 일때도               
                    if self.chejan['미결제청산가능수량'] == 1 :
                        
                        self.chejan['손절가격'] = self.chejan['체결가격'] + self.t_ohlcv.N.iloc[-2] * 2 \
                            if self.chejan['매도수구분'] == 1 \
                            else self.chejan['체결가격'] - self.t_ohlcv.N.iloc[-2] * 2
                        
                    elif self.chejan['미결제청산가능수량'] > 3 :

                        self.chejan['손절가격'] = self.chejan['평균가격']
                    """

                    self.chejan['손절가격'] = self.chejan['체결가격'] + self.t_ohlcv.N.iloc[-2] * 2 \
                        if self.chejan['매도수구분'] == 1 \
                        else self.chejan['체결가격'] - self.t_ohlcv.N.iloc[-2] * 2

                    #########################

                    self.chejan['피라미딩가격'] = self.chejan['체결가격'] - self.t_ohlcv.N.iloc[-2] \
                        if self.chejan['매도수구분'] == 1 \
                        else self.chejan['체결가격'] + self.t_ohlcv.N.iloc[-2]

                    #########################

                    self.chejan_event_loop = True


                elif self.chejan['청산수량'] > 0:


                    if self.chejan['미결제청산가능수량'] == 0:
                        
                        # 초기화
                        self.chejan['평균가격'] = 0
                        self.chejan['손절가격'] = 0
                        self.chejan['피라미딩가격'] = 0

                        # 오픈 포지션 초기화
                        self.trade.drop(self.trade.index, axis=0, inplace=True)

                        # 체잔(주문) 이벤트 루프
                        self.chejan_event_loop = True


                print(f"[체잔] 미결제청산가능수량: {self.chejan['미결제청산가능수량']}, "
                      f"신규수량: {self.chejan['신규수량']}, 청산수량: {self.chejan['청산수량']}, "
                      f"체결가: {self.chejan['체결가격']}, 평단가: {self.chejan['평균가격']} 손절가: {self.chejan['손절가격']}, 피라미딩가: {self.chejan['피라미딩가격']:.2f}, N[-2]: {self.t_ohlcv.N.iloc[-2]:.2f} ")




                pass

            # 미결제잔고내역조회 (opw30003)
            # 체결후 포지션(잔고) 업데이트
            #self.req_opw30003()




    def _calc_breakouts(self, df):

        # 시스템 1
        df['S1_EL'] = df['Close'].rolling(self.turtle['sys1_entry']).max()
        df['S1_ExL'] = df['Close'].rolling(self.turtle['sys1_exit']).min()
        df['S1_ES'] = df['Close'].rolling(self.turtle['sys1_entry']).min()
        df['S1_ExS'] = df['Close'].rolling(self.turtle['sys1_exit']).max()

        return df

    def _calc_N(self, df):

        df['N'] = ta.atr(df['High'], df['Low'], df['Close'], length=20, mamode='sma')

        return df

    def _calc_ma(self, df):

        df['ma5'] = df['Close'].rolling(window=5).mean()
        df['ma20'] = df['Close'].rolling(window=20).mean()
        df['ma40'] = df['Close'].rolling(window=40).mean()


        return df


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
            volume = int(self._get_comm_real_data(sCode, 15)) # (+ 매수체결, - 매도체결)
            l_volume = volume if volume > 0 else 0
            c_volume = abs(volume)  # 거래량


            # 체결강도


            # 틱 카운트 +1 증가
            # 1(시가),2,3,4,0(종가)
            self.t_cnt += 1

            gb = self.t_cnt % self.tick_unit

            # 1: 새틱차트 생성
            # 새틱차트 시작, 새틱차트 생성
            if gb == 1:

                # print(f"틱 카운트: {self.t_cnt}, 구분: {gb}, 새틱차트 생성, 시작시간: {c_dt}, 시가(현재가): {c_price:.2f}, 시작수량: {c_volume} ")
                # 체결강도


                ohlcv = pd.DataFrame(
                    {'date_time': n_dt, 'Open': c_price, 'High': 0, 'Low': 100000,
                     'Close': c_price, 'Volume': c_volume, 'S': l_volume}, index=[0])
                self.t_ohlcv = pd.concat([self.t_ohlcv, ohlcv], ignore_index=True)

                # Breakouts과 N계산, 5/10/20 이평선
                df = self.t_ohlcv[-50:]
                df = self._calc_breakouts(df)
                df = self._calc_N(df)
                df = self._calc_ma(df)

                # ohlcv에 시스템 1의 Breakouts 추가
                self.t_ohlcv.S1_EL.iloc[-2] = df.S1_EL.iloc[-2]
                self.t_ohlcv.S1_ES.iloc[-2] = df.S1_ES.iloc[-2]
                self.t_ohlcv.S1_ExL.iloc[-2] = df.S1_ExL.iloc[-2]
                self.t_ohlcv.S1_ExS.iloc[-2] = df.S1_ExS.iloc[-2]

                # ohlcv에 N 추가
                self.t_ohlcv.N.iloc[-2] = df.N.iloc[-2]

                # ohlcv에 이평선 추가
                self.t_ohlcv.ma5.iloc[-2] = df.ma5.iloc[-2]
                self.t_ohlcv.ma20.iloc[-2] = df.ma20.iloc[-2]
                self.t_ohlcv.ma40.iloc[-2] = df.ma40.iloc[-2]


                # 체결강도를 계산해서 업데이트
                s_volume = self.t_ohlcv.Volume.iloc[-2] - self.t_ohlcv.S.iloc[-2]
                self.t_ohlcv.S.iloc[-2] = round(self.t_ohlcv.S.iloc[-2] / s_volume * 100, 0) if s_volume != 0 else -100



                # 마지막차트 출력
                print(f"[{self.tick_unit}틱-{self.t_ohlcv.index[-2]}] 체결시간: {self.t_ohlcv.date_time.iloc[-2]}, "
                      f"시가: {self.t_ohlcv.Open.iloc[-2]:.2f}, 고가: {self.t_ohlcv.High.iloc[-2]:.2f}, 저가: {self.t_ohlcv.Low.iloc[-2]:.2f}, 종가: {self.t_ohlcv.Close.iloc[-2]:.2f}, "
                      f"거래량: {self.t_ohlcv.Volume.iloc[-2]}, 체결강도: {self.t_ohlcv.S.iloc[-2]}, N: {self.t_ohlcv.N.iloc[-2]}")

                # 자동 선물 매매
                if self.system_running:
                    self._run_system()


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

                # 매수 수량 업데이트
                self.t_ohlcv.S.iloc[-1] += l_volume

        pass

    def _run_system(self):



        # 현재가격
        price = self.t_ohlcv.Close.iloc[-2]

        # 시스템 1
        S1_EL = self.t_ohlcv.S1_EL.iloc[-2]
        S1_ES = self.t_ohlcv.S1_ES.iloc[-2]

        S1_ExL = self.t_ohlcv.S1_ExL.iloc[-2]
        S1_ExS = self.t_ohlcv.S1_ExS.iloc[-2]

        N = self.t_ohlcv.N.iloc[-2]

        # 5/10/20 이평선
        ma5 = self.t_ohlcv.ma5.iloc[-2]
        ma20 = self.t_ohlcv.ma20.iloc[-2]
        ma40 = self.t_ohlcv.ma40.iloc[-2]

        # 이평선 정배열/역배열
        l_ma = True if price > ma5 and ma5 > ma20 and ma20 > ma40 else False # 정배열
        s_ma = True if price < ma5 and ma5 < ma20 and ma20 < ma40 else False # 역배열



        if self.chejan_event_loop:

            # 포지션이 없으면
            if self.chejan['미결제청산가능수량'] == 0 :

                if price == S1_EL and l_ma:

                    # 시장가 매수 주문
                    self.send_order2("매수 진입", self.accno, "", self.ticker, self.get_order_gb('매수'),
                                     self.get_order_type('시장가'), 1, '', \
                                     '0', '', '0', '')

                    self.chejan_event_loop = False

                    print(f"[롱포지션 진입]")

                elif price == S1_ES and s_ma:

                    # 시장가 매도 주문
                    self.send_order2("매도 진입", self.accno, "", self.ticker, self.get_order_gb('매도'),
                                     self.get_order_type('시장가'), 1, '', \
                                     '0', '', '0', '')

                    self.chejan_event_loop = False

                    print(f"[숏포지션 진입]")

            # 포지션이 있으면
            else:

                if self.chejan['미결제매도수구분'] == 2:  # 롱 (매수)

                    # Check to exit existing long position
                    if price == S1_ExL:

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[롱포지션 청산] S1_ExL: {S1_ExL}")

                    elif price < ma20:

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[롱포지션 청산] ma20: {ma20}")

                    elif price <= self.chejan['손절가격']:

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[롱포지션 손절]")

                    # Check to pyramid existing position
                    elif self.chejan['미결제청산가능수량'] <= self.turtle['size_limit']:

                      if price >= self.chejan['피라미딩가격'] and l_ma:

                          # 시장가 매수 주문
                          self.send_order2("롱피라미딩", self.accno, "", self.ticker, self.get_order_gb('매수'),
                                           self.get_order_type('시장가'), 1, '', \
                                           '0', '', '0', '')

                          self.chejan_event_loop = False

                          print(f"[롱피라미딩]")




                elif self.chejan['미결제매도수구분'] == 1:  # 숏 (매도)

                    # Check to exit existing long position
                    if price == S1_ExS :

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[숏포지션 청산] S1_ExS: {S1_ExS}")

                    elif price > ma20:

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[숏포지션 청산] ma20: {ma20}")


                    elif price >= self.chejan['손절가격']:

                        self.position_close()

                        self.chejan_event_loop = False

                        print(f"[숏포지션 손절]")

                    # Check to pyramid existing position
                    elif self.chejan['미결제청산가능수량'] <= self.turtle['size_limit']:

                        if price < self.chejan['피라미딩가격'] and s_ma:
                            # 시장가 매도 주문
                            self.send_order2("숏피라미딩", self.accno, "", self.ticker, self.get_order_gb('매도'),
                                             self.get_order_type('시장가'), 1, '', \
                                             '0', '', '0', '')

                            self.chejan_event_loop = False

                            print(f"[숏피라미딩]")




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

    def send_order2(self, order_name, account_num, password, code, ls_gb, order_type, qty, price, stop_gb, stop_price, limit_gb, limit_price):

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

        ret = self.comm_rq_data(order_name, "opw10008", "", self.get_screen_number())

    def on_receive_msg(self, screen_number, rq_name, tr_code, msg):
        pass

    def position_close(self):

        if self.chejan['미결제매도수구분'] == 2:

            # 시장가 전량 매도
            self.send_order2("일괄매도", self.accno, "", self.ticker, self.get_order_gb('매도'),
                             self.get_order_type('시장가'), self.chejan['미결제청산가능수량'], '', \
                             '0', '', '0', '')

        elif self.chejan['미결제매도수구분'] == 1:

            # 시장가 전량 매수
            self.send_order2("일괄매수", self.accno, "", self.ticker, self.get_order_gb('매수'),
                             self.get_order_type('시장가'), self.chejan['미결제청산가능수량'], '', \
                             '0', '', '0', '')


class Fire(QMainWindow, main_form):

    def __init__(self):
        super().__init__()

        #QMessageBox.about(self, "message", "Fire.__init__")

        self.setupUi(self)


        # Broker 인스턴스 생성
        self.kiwoom = Broker(self, "MNQU24", 360)

        # 키움서버 접속
        self.kiwoom.comm_connect()

        # 계좌번호 설정
        self.kiwoom.set_account_num()

        # 틱차트 요청
        self.kiwoom.req_opc10001()

        ## 메인윈도우 이벤트 처리
        self.set_event_handler()


    def set_event_handler(self):
        # 자동 매매 시작/종료
        self.menu_trading_start.triggered.connect(self.action_trading_start)
        self.menu_trading_end.triggered.connect(self.action_trading_end)

        # 주문
        self.menu_position_close.triggered.connect(self.kiwoom.position_close)

        # TR
        self.menu_opw30003.triggered.connect(self.kiwoom.req_opw30003)


        pass

    def action_trading_start(self):

        self.kiwoom.system_running = True

    def action_trading_end(self):

        self.kiwoom.system_running = False



if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        window = Fire()
        window.show()

        sys.exit( app.exec_() )
    except Exception as e:
        print(e)
