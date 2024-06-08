import pandas as pd
import numpy as np



opw3003_S = {'매도수량': 0, '매수수량': 0, '총평가금액': 0, '실현수익금액': 0, '총약정금액': 0, '총수익율': 0}
opw30003_List = []

class Position:

    def __init__(self):

        self.total = pd.Series(opw3003_S)
        #self.codes = pd.DataFrame(opw3003_S)

    def get_total(self):

        print(self.total)


nq_position = Position()

#nq_position.get_total()

#qty = nq_position.total['매도수량']
nq_position.total['매도수량'] = 3
nq_position.total['매수수량'] = 5
nq_position.total[2] = 10

size = nq_position.total.size
sum = nq_position.total.sum()

# 행추가
nq_position.total['청산가능'] = 100

# 행삭제
nq_position.total = nq_position.total.drop('총수익율')

#https://www.snugarchive.com/blog/python-pandas-series/
# 1차원 배열
arr = np.arange(5)
s1 = pd.Series(arr)

# list
ls = [10, 50, 40, 70, 100]
s2 = pd.Series(ls)

ls = ['황선우', '황민우', '황현서', '황인호']
s3 = pd.Series(ls)

# 딕셔너리
dic = {'큰아들': '황선우', '작은아들': '황민우', '엄마': '황현서', '아빠': '황인호'}
s4 = pd.Series(dic)

# 지정하기
data = np.arange(5)

s5 = pd.Series(data, index=[x for x in '할허로이드'])

# 조건으로 데이터 선택

s6 = s2[s2 > 75]

# 데이터프레임 조건 검색
# 미체결이 > 0 이상인 행의 주문 번호 추출하기


import pandas as pd

df = pd.DataFrame([{"country":"한국","population":500},{"country":"미국","population":450},{"country":"싱가폴","population":705},
                   {"country":"호주","population":878},{"country":"베트남","population":660},{"country":"대만","population":808}])

df2 = df[df['population']>800]

s1 = df2['country']



print("된다! 하면된다! 할수있다! Just Do It Now")

