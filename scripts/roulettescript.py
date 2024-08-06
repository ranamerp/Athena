colors = {'00':'green', 0:'green',1:'red',2:'black',3:'red',4:'black',5:'red',6:'black',7:'red',
            8:'black',9:'red',10:'black',11:'black',12:'red',13:'black',14:'red',15:'black',16:'red',
            17:'black',18:'red',19:'red',20:'black',21:'red',22:'black',23:'red',24:'black',25:'red',
            26:'black',27:'red',28:'black',29:'black',30:'red',31:'black',32:'red',33:'black',34:'red',
            35:'black',36:'red'}

colors2 = {'black': '⚫', 'red': '🔴', 'green': '🟢'}

order = [0, 28, 9, 26, 30, 11, 7, 20, 32, 17, 5, 22, 34, 15, 3, 24, 36, 13, 1, '00', 27, 10, 25, 29, 12, 8, 19, 31, 18, 6, 21, 33, 16, 4, 23, 35, 14, 2]

l = []
col = 1
# [number, color, even/odd, high/low, column, dozen]
for i in range(1,37):
	if col > 3:
		col = 1

	curr = [i, colors[i]]

	if i % 2 == 0:
		curr.append("even")
	else:
		curr.append("odd")

	if i in range(1, 19):
		curr.append("low")
	else:
		curr.append("high")

	curr.append(col)

	if i in range(1, 13):
		curr.append(1)
	elif i in range(13, 25):
		curr.append(2)
	else:
		curr.append(3)
	
	l.append(curr)

	col += 1

ll = []
for n in order:
	ll.append(colors2[colors[n]] + str(n))
print(ll)
