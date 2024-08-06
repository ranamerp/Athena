import enum
from random import *
from collections import deque
from millify import millify, prettify



class Suit(enum.Enum):
	Hearts = '♥'
	Clubs = '♣'
	Diamonds = '♦'
	Spades = '♠'

class Rank(enum.Enum):
	Two = '2'
	Three = '3'
	Four = '4'
	Five = '5'
	Six = '6'
	Seven = '7'
	Eight = '8'
	Nine = '9'
	Ten = 'X'
	Jack = 'J'
	Queen = 'Q'
	King = 'K'
	Ace = 'A'

SUITS = [Suit.Diamonds, Suit.Clubs, Suit.Hearts, Suit.Spades]
RANKS = [Rank.Two, Rank.Three, Rank.Four, Rank.Five, Rank.Six, Rank.Seven, Rank.Eight, Rank.Nine, Rank.Ten, Rank.Jack, Rank.Queen, Rank.King, Rank.Ace]


class Card:
	def __init__(self, rank: Rank, suit: Suit, hidden=False):
		self.rank = rank
		self.suit = suit
		self.hidden = hidden

	def __repr__(self):
		if not self.hidden:
			return f'{self.rank.value}{self.suit.value}'
		else:
			return '??'
				
class Deck:
	def __init__(self, count=1):
		self.initialCount = count
		self.cards = deque()
		for i in range(count):
			for s in SUITS:
				for r in RANKS:
					self.cards.append(Card(r, s))
		
		self.shuffle(1)

	def __len__(self):
		return len(self.cards)

	def __add__(self, other):
		self.cards.extend(other.cards)
		return self

	def rebuild(self):
		self.cards.clear()
		for i in range(self.initialCount):
			for s in SUITS:
				for r in RANKS:
					self.cards.append(Card(r, s))
		
		self.shuffle(1)

	def printDeck(self):
		for card in self.cards:
			print(card)
		print(len(self.cards))

	def draw(self, hidden=False):
		try:
			newCard: Card = self.cards.pop()
			newCard.hidden = hidden
			return newCard
		except IndexError:
			return None
	
	def shuffle(self, times=1):
		for i in range(times):
			shuffle(self.cards)

		return i + 1


	def fillHand(self, handSize, hand):
		for i in range(handSize):
			hand.addCard(self.draw())

class Hand:
	def __init__(self, cards=None):
		self.cards = cards or deque()

	def __repr__(self):
		hand = ""
		for card in self.cards:
				hand += str(card) + ' '
		return hand

	def __len__(self):
		return len(self.cards)

	def addCard(self, card):
		self.cards.append(card)
	
	def addCards(self, cards):
		self.cards.extend(cards)

	def hide(self, index):
		self.cards[index].hidden = True

	def unhide(self, index):
		self.cards[index].hidden = False

	def calculateValue(self, addHidden=False):
		total = 0
		for card in self.cards:
			if card.hidden and not addHidden:
				continue
			elif card.rank.name == 'Ace':
				total += 15
			else:
				try:
					conv = int(card.rank.value)
					total += 5
				except ValueError:
					total += 10
			
		return total

class Player:
	def __init__(self, name, mention, id, hand=None, empty=False, wager=0, status = None):
		self.status = status
		self.empty = empty
		self.name = name
		self.mention = mention
		self.id = id
		self.wager = wager
		self.hand = hand or Hand()
	
	def __str__(self):
		return self.name

	def __eq__(self, o: object) -> bool:
		return self.name == o.name and self.id == o.id

	def __hash__(self) -> int:
		return hash(self.name + str(self.id))

	def toString(self, bet=False):
		strRep = []
		for i in range(3):
			strRep.append('')
			for j in range(i * 3, (i + 1) * 3):
				try:
					strRep[i] += str(self.hand.cards[j]) + ' '
				except IndexError:
					strRep[i] += '   '
			strRep[i] = strRep[i].rstrip()
		strRep.reverse()
		if self.empty:
			strRep.append('        ')
		else:
			if not bet or (self.name == 'Dealer' and self.id == 1):
				strRep.append(f'Sum: {self.hand.calculateValue()}')
			else:
				try:
					strRep.append(f'$: {millify(self.wager, precision=(3 - len(millify(self.wager)[:-1])))}')
				except ValueError:
					strRep.append(f'$: {self.wager[:5]}')

		strRep.append(self.name[:8])

		for i in range(len(strRep)):
			strRep[i] += (' ' * (8 - len(strRep[i])))

		return strRep

class Table:
	def __init__(self):
		self.emptySeat = Player('        ', 'NA', 'NA', empty=True)
		self.table = [[self.emptySeat, self.emptySeat, self.emptySeat],
					  [self.emptySeat, self.emptySeat, self.emptySeat],
					  [self.emptySeat, self.emptySeat, self.emptySeat]]
		self.seperator = ['   ', '   ', ' | ', ' | ', ' | ']
		self.emptySeperator = ['   ', '   ', '   ', '   ', '   ']
		self.emptyRow = ['        ', '   ', '        ', '   ', '        ']

	def addPlayer(self, row, col, player):
		self.table[row][col] = player
	
	def addPlayerInNextEmpty(self, player, protected=0):
		breakOuter = False
		for i in range(3):
			if i != protected:
				for j in range(3):
					if self.table[i][j] == self.emptySeat:
						self.table[i][j] = player
						breakOuter = True
						break
				
				if breakOuter:
					break

	def removePlayer(self, row, col):
		self.table[row][col] = self.emptySeat

	def removePlayerByID(self, id):
		playerRemoved = False
		for i in range(3):
			for j in range(3):
				if self.table[i][j] != self.emptySeat and self.table[i][j].id == id:
					self.table[i][j] = self.emptySeat
					playerRemoved = True
		
		return playerRemoved
	
	def swapPlayer(self, oldRow, oldCol, newRow, newCol):
		first = self.table[oldRow][oldCol]
		second = self.table[newRow][newCol]
		self.table[oldRow][oldCol] = second
		self.table[newRow][newCol] = first

	def replacePlayerByID(self, id, newPlayer: Player):
		playerRemoved = False
		for i in range(3):
			for j in range(3):
				if self.table[i][j] != self.emptySeat and self.table[i][j].id == id:
					self.table[i][j] = newPlayer
					playerReplaced = True
		
		return playerReplaced


	def fillEmpty(self, protected=0):
		newTable = [[self.emptySeat, self.emptySeat, self.emptySeat],
					[self.emptySeat, self.emptySeat, self.emptySeat],
					[self.emptySeat, self.emptySeat, self.emptySeat]]
		
		try:
			newTable[protected] = self.table[protected]
		except IndexError:
			pass
		

		players = []
		for i in range(3):
			if i != protected:
				for j in range(3):
					if self.table[i][j] != self.emptySeat:
						players.append(self.table[i][j])

		for p in players:
			breakOuter = False
			for i in range(3):
				if i != protected:
					for j in range(3):
						if newTable[i][j] == self.emptySeat:
							newTable[i][j] = p
							breakOuter = True
							break
					
					if breakOuter:
						break
		
		self.table = newTable

	def checkIfColumnEmpty(self, column):
		for i in range(3):
			if self.table[i][column] != self.emptySeat:
				return False
		return True 

	def checkIfRowEmpty(self, row):
		for i in range(3):
			if self.table[row][i] != self.emptySeat:
				return False
		return True

	def compileTable(self, bet=False):
		grid = []
		for i in range(3):
			for j in range(5):
				if i == 0:
					sep = self.emptySeperator
				else:
					sep = self.seperator
				
				grid.append([self.table[i][0].toString(bet=bet)[j], sep[j], self.table[i][1].toString(bet=bet)[j], sep[j], self.table[i][2].toString(bet=bet)[j]])

			if i != 2:
				grid.append(self.emptyRow)
				grid.append(self.emptyRow)
		
		if self.checkIfColumnEmpty(2):
			for i in range(len(grid)):
				grid[i] = grid[i][:3]
		
		if self.checkIfColumnEmpty(1):
			for i in range(len(grid)):
				grid[i] = grid[i][0]
		
		toRemove = []
		for i in range(19):
			grid[i] = ''.join(grid[i])
			if grid[i].replace('|', '').isspace(): 
				if (i == 5 or i == 6) and not self.checkIfRowEmpty(1):
					continue
				elif (i == 12 or i == 13) and not self.checkIfRowEmpty(2):
					continue
				else:
					toRemove.append(i)

		for n in reversed(toRemove):
			grid.pop(n)

		strRep = ''
		for r in grid:
			strRep += f"`{r}`\n"
		
		return strRep