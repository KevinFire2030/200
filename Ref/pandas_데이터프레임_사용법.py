#https://hogni.tistory.com/9

# 판다스 라이브러리 임포트

import pandas as pd

"""
# plotly express에 내장되어있는 gapminder 데이터프레임을 사용하겠습니다.
import plotly.express as px

df = px.data.gapminder()


df2 = df[df['year']==1952]

country = df2['country']
"""

# 두가지 조건 만족

#df3 = df[(df['year']>1952 & df['year'] < 1960)]


DF = pd.DataFrame({'name' : ['Minsoo','Minju','Yeomin','Hyeri','Junghun','Sunny','Bummee','Luna'],
                   '나이'  : [33,25,19,25,32,36,23,36],
                   'sex'  : ['M','W','W','W','M','W','M','W'],
                   'score1': [91,50,69,98,72,85,43,61],
                   'score2': [65,77,56,82,79,91,71,63],
                   'time' : [30,95,64,88,34,69,15,25],
                   })

df3 = DF[(DF['sex']=='W') & (DF['score1']<70)]

df4 = DF[(DF['score1']>=80)|(DF['score2']>=80)]

df5 = DF[((DF['나이']>=20) & (DF['나이']<30))|(DF['time']<40)]

# 데이터 접근
DF.loc[5, '나이'] = 48

# 행과 열 삭제하기
DF.drop(1, axis=0, inplace=True)
DF.drop('나이', axis=1, inplace=True)

# 행과 열 선택하기
DF.loc[1, 'name'] = '황선우'

print(DF.info())

print("된다! 하면된다! 할수있다! Just Do It Now")