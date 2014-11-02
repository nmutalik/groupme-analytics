import flask, requests, json, pygal
from flask import Flask, request
from pygal.style import LightSolarizedStyle
from collections import defaultdict
import logging
logging.basicConfig(filename='example.log',level=logging.DEBUG)

app = Flask(__name__)

@app.route('/')
def root():
    return flask.redirect("https://oauth.groupme.com/oauth/authorize?client_id=HAHBp8EjjOLgAp89KFdgU0s0M3CGK9KQBYWg1SjG5FJa4u7u")

@app.route('/dashboard')
def dash():
	access_token = request.args.get('access_token')
	if access_token:
		groups = requests.get('https://api.groupme.com/v3/groups?per_page=100&access_token={0}'.format(access_token)).json()['response']
		return flask.render_template('dashboard.html', groups=groups, access_token=access_token)
	return flask.redirect('/')

@app.route('/group/<group_id>')
def group(group_id):
	access_token = request.args.get('access_token')
	if access_token:
		memory = requests.get('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id)).json()
		if not memory:
			group = requests.get('https://api.groupme.com/v3/groups/{0}?access_token={1}'.format(group_id, access_token)).json()['response']
			members = defaultdict(list)
		 	for m in group['members']:
		 		if m['image_url']:
		 			members[m['user_id']].append(m['image_url'] + '.avatar')
		 		else:
		 			members[m['user_id']].append("https://i.groupme.com/sms_avatar.avatar")
		 		members[m['user_id']].append(m['nickname'])
			members['system'] = ["",'system']
			logging.debug(members)
			likes = defaultdict(lambda: defaultdict(int))
			posts = defaultdict(int)
			messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&access_token={1}'.format(group_id, access_token))
			latest = messages.json()['response']['messages'][0]['id']
			while messages.status_code == 200:
				for m in messages.json()['response']['messages']:
					if m['user_id'] not in members:
						members[m['user_id']] = [(m['avatar_url'] + ".avatar") if m['avatar_url'] else "", m['name']]
					for f in m['favorited_by']:
						likes[m['user_id']][f] += 1
					posts[m['user_id']] += 1
				messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&before_id={1}&access_token={2}'.format(group_id, m['id'], access_token))
			memory = requests.put('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id),
				data=json.dumps({ 
					"members": members, 
					"likes": likes if likes else {"system":{"system":0}}, 
					"group": group, 
					"latest": latest,
					"posts": posts})).json()
		else:
			messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?after_id={1}&limit=100&access_token={2}'.format(group_id, memory['latest'], access_token))
			while messages.status_code == 200:
				for m in messages.json()['response']['messages']:
					for f in m['favorited_by']:
						memory['likes'][m['user_id']][f] += 1
					memory['posts'][m['user_id']] += 1
				if messages.json()['response']['messages']:
					messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&after_id={1}&access_token={2}'.format(group_id, messages.json()['response']['messages'][-1]['id'], access_token))
				else:
					break
			requests.put('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id),
				data=json.dumps(memory))
		array = makeArrayFromDictionary(memory['members'], memory['likes'])
		chart1 = renderChartFromArray(array, memory['members'], "Likes Given")
		chart2 = renderChartFromArray(zip(*array), memory['members'], "Likes Received")
		print map(lambda x: memory['members'][x], sorted(memory['members']))
		print [x for x in enumerate(array)]
		return flask.render_template('group.html', array=enumerate(array), members=map(lambda x: memory['members'][x], sorted(memory['members'])), group=memory['group'], chart1=chart1, chart2=chart2)			
	return flask.redirect('/')

@app.route('/delete/<group_id>')
def delete(group_id):
	return requests.delete('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id)).text 

def makeArrayFromDictionary(members, likes):
	print members
	print likes
	member_ids = sorted(members.keys())
	array = [x[:] for x in [[0]*len(member_ids)]*len(member_ids)]
	for k, v in likes.iteritems():
		for i, l in v.iteritems():
			array[member_ids.index(k)][member_ids.index(i)] = l
	return array

def renderChartFromArray(array, members, title):
	names_x = sorted(members.keys())
	names_y = names_x[:]
	stackedbar_chart = pygal.StackedBar(height=400+20*len(members),style=LightSolarizedStyle, x_label_rotation=30)
	stackedbar_chart.title = title
	stackedbar_chart.x_labels = map(lambda x: members[x][1].split()[0], names_x)
	for i, v in enumerate(names_y):
		stackedbar_chart.add(members[v][1].split()[0], array[i])
	return stackedbar_chart.render(is_unicode=True)

if __name__ == "__main__":
	app.debug = True
	app.run()

