
steps = [

{'flavor':   ['Welcome to your adventure!',
 'Are you excited? I\'m excited.'],
 'question': 'If you are ready to start, reply \'ready\'',
 'answer': 'ready',
 },

{'flavor':   ['We are off to the races!',
 'Go in a direction until you find something cool.',
 'This thing is really awesome.'],
 'question': 'What does the awesome thing have written on it?',
 'answer': 'hotsauce',
 },

{'flavor':   ['Congratulations! You made it.',
 'You found all of the things.'],
 'question': 'If you wish to do this again, text \'start\'. Otherwise, safe travels.',
 'answer': 'NOANSWER',
 },

]

if __name__ == '__main__':
	for item in steps:
		for line in item['flavor'] + [item['question'],]:
			print '%4d'%len(line), line
		print
		print
