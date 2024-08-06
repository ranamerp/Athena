teams_list = ["Man Utd", "Man City", "T Hotspur"]
data = [[1, 2, 1],  [0, 16, 0], [2, 4, 2]]

row_format ="{:>15}" * (len(teams_list) + 1)

print(row_format.format("", *teams_list))

for team, row in zip(teams_list, data):
	print(row_format.format(team, *row))