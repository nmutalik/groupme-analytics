import flask, requests, json
from flask import Flask, request
from collections import defaultdict
import plotly.plotly as py
from plotly.graph_objs import *
py.sign_in("nmutalik", "bwbicp31y0")
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
		memory = {}
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
			members['system'] = ["",'GroupMe']
			likes_given = defaultdict(lambda: defaultdict(int))
			likes_received = defaultdict(lambda: defaultdict(int))
			posts = defaultdict(int)
			messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&access_token={1}'.format(group_id, access_token))
			latest = messages.json()['response']['messages'][0]['id']
			while messages.status_code == 200:
				for m in messages.json()['response']['messages']:
					if m['user_id'] not in members:
						members[m['user_id']] = [(m['avatar_url'] + ".avatar") if m['avatar_url'] else "", m['name']]
					for f in m['favorited_by']:
						likes_given[f][m['user_id']] += 1
						likes_received[m['user_id']][f] += 1
					posts[m['user_id']] += 1
				messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&before_id={1}&access_token={2}'.format(group_id, m['id'], access_token))
			memory = requests.put('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id),
			  data=json.dumps({ 
			      "members": members, 
			      "likes_given": likes_given if likes_given else {"system":{"system":0}}, 
			      "likes_received": likes_received if likes_received else {"system":{"system":0}}, 
			      "group": group, 
			      "latest": latest,
			      "posts": posts})).json()
			memory = { 
						"members": members, 
						"likes_given": likes_given if likes_given else {"system":{"system":0}}, 
						"likes_received": likes_received if likes_received else {"system":{"system":0}}, 
						"group": group, 
						"latest": latest,
						"posts": posts
					}
		else:
			messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?after_id={1}&limit=100&access_token={2}'.format(group_id, memory['latest'], access_token))
			memory['group'] = requests.get('https://api.groupme.com/v3/groups/{0}?access_token={1}'.format(group_id, access_token)).json()['response']
			while messages.status_code == 200 and messages.json()['response']['messages']:
				for m in messages.json()['response']['messages']:
					if m['user_id'] not in memory['members']:
						memory['members'][m['user_id']] = [(m['avatar_url'] + ".avatar") if m['avatar_url'] else "", m['name']]
					memory['likes_given'] = defaultdict(lambda: defaultdict(int),
						{key: defaultdict(int, value.iteritems()) for key, value in memory['likes_given'].iteritems()})
					memory['likes_received'] = defaultdict(lambda: defaultdict(int),
						{key: defaultdict(int, value.iteritems()) for key, value in memory['likes_received'].iteritems()})
					memory['posts'] = defaultdict(int, memory['posts'].iteritems())
					for f in m['favorited_by']:
						memory['likes_given'][f][m['user_id']] += 1
						memory['likes_received'][m['user_id']][f] += 1
					memory['posts'][m['user_id']] += 1
				memory['latest'] = messages.json()['response']['messages'][-1]['id']
				messages = requests.get('https://api.groupme.com/v3/groups/{0}/messages?limit=100&after_id={1}&access_token={2}'.format(group_id, memory['latest'], access_token))
			requests.put('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id),
				data=json.dumps(memory))
		renderer = renderChartMaker(memory['members'], memory['group'])
		smallcharts, charts, bigcharts = [], [], []
		members = memory['members'].keys()
		likesGivenData = sumLikes(memory['likes_given'])
		likesReceivedData = sumLikes(memory['likes_received'])
		total = sum(likesGivenData.values())
		likeWorth = {key: float(total)/likesGivenData.get(key, total) for key in members}
		netWorth = calculateNetWorth(memory['likes_received'], likeWorth, members)
		netWorthPerPost = {key: netWorth[key]/memory['posts'].get(key, 1) for key in members}
		charts.append(renderer.renderBarChart(memory['posts'], "Posts Made", 0))
		charts.append(renderer.renderBarChart([likesReceivedData, likesGivenData], "Likes Received and Given", 1, ["Likes Received", "Likes Given"]))
		charts.append(renderer.renderBarChart(
			[
				{key: float(likesReceivedData.get(key, 0))/memory['posts'].get(key, 1) for key in memory['members'].keys()},
				{key: float(likesGivenData.get(key, 0))/memory['posts'].get(key, 1) for key in memory['members'].keys()}
			],
			"Likes Received and Given Per Post Made", 3, ["Likes Received Per Post Made", "Likes Given Per Post Made"]))
		charts.append(renderer.renderBarChart({key: float(likesGivenData.get(key, 0))/float(likesReceivedData.get(key, 1)) for key in members},
			"Likes Given Per Like Received", 4))
		charts.append(renderer.renderBarChart(likeWorth, "Comparative Like Worth", 5))
		charts.append(renderer.renderBarChart(netWorth, "Net Worth", 6))
		charts.append(renderer.renderBarChart(netWorthPerPost, "Net Worth Per Post", 7))
		# charts.extend(renderAllegiances(renderer, memory['likes_given'], memory['likes_received'], memory['members'], 8))
		bigcharts.append(renderer.renderPercentHeatmap(lambda x,y: memory['likes_given'].get(x, {}).get(y, 0), "Likes Given", 8))
		bigcharts.append(renderer.renderPercentHeatmap(lambda x, y: float(memory['likes_given'].get(x, {}).get(y, 0))/memory['posts'].get(y, 1), "Percent of Others Posts Liked", 9))
		bigcharts.append(renderer.renderPercentHeatmap(lambda x, y: float(memory['likes_given'].get(x, {}).get(y, 0))/likesGivenData.get(x, 1), "Percent of Likes Given", 10))
		bigcharts.append(renderer.renderBarChart({key: sum(map(lambda x: float(memory['likes_given'].get(key,{}).get(x,0))/memory['posts'].get(x, 1), members))/len(members) for key in members},
			"Average Percent of Others Posts Liked", 11))
		bigcharts.append(renderer.renderBarChart({key: sum(map(lambda x: float(memory['likes_given'].get(x, {}).get(key, 0))/likesGivenData.get(x, 1), members))/len(members) for key in members},
			"Average Percent of Others Likes Received", 12))
		# print likesPerPost(likesGivenData, memory['posts'])
		# charts.append(renderer.renderBarChart(likesPerPost(likesGivenData, memory['posts']), "Likes Given per Post Made", 2))
		# charts.append(renderer.renderBarChart(likesPerPost(likesReceivedData, memory['posts']), "Likes Received per Post Made", 3))
		return flask.render_template('group.html', group=memory['group'], smallcharts=smallcharts, charts=charts, bigcharts=bigcharts)          
	return flask.redirect('/')

@app.route('/delete/<group_id>')
def delete(group_id):
	return requests.delete('https://groupy.firebaseio.com/groups/{0}.json'.format(group_id)).text 

def renderAllegiances(renderer, likes_given, likes_received, members, startIndex):
	output = []
	for member_id, name in members.iteritems():
		if member_id == 'system':
			continue
		output.append(renderer.renderBarChart([likes_given.get(member_id,{}), likes_received.get(member_id, {})], name[1], startIndex, ["Likes Given", "Likes Received"]))
		startIndex += 1
	return output


def calculateNetWorth(likes_received, like_worth, members):
	return {key: sum(map(lambda x: likes_received[key][x]*like_worth[x], likes_received.get(key, {}).keys())) for key in members}

def makeArrayFromDictionary(members, likes):
	member_ids = sorted(members.keys())
	array = [x[:] for x in [[0]*len(member_ids)]*len(member_ids)]
	for k, v in likes.iteritems():
		for i, l in v.iteritems():
			array[member_ids.index(k)][member_ids.index(i)] = l
	return array

def sumLikes(dictionary):
	output = defaultdict(int)
	for k, v in dictionary.iteritems():
		output[k] = sum(v.values())
	return output

def likesPerPost(likes, posts):
	return {key: float(value)/posts[key] for key, value in sorted(likes.iteritems(), key=lambda x: float(x[1])/posts[x[0]])}

class renderChartMaker:
	def __init__(self, members, group):
		 self.members = members
		 self.group = group

	def renderPercentHeatmap(self, function, title, index):
		members = self.members.keys()
		bars = [Heatmap(
				x=map(lambda x: self.members[x][1], members),
				y=map(lambda x: self.members[x][1], members),
				z=map(lambda x: map(lambda y: function(x, y), members), members)
			)]
		layout = Layout(
				title=title,
				margin=Margin(
					l=200,
					r=50,
					b=150,
					t=50,
					pad=4
				)
			)

		return py.plot(Figure(data=Data(bars), layout=layout), filename=self.group['id'] + '-' + str(index), fileopt="overwrite", auto_open=False)

	def renderBarChart(self, raw_data, title, index, names="", barmode=None):
		if isinstance(raw_data, dict):
			raw_data = [raw_data]
		if not names:
			names = title
		if isinstance(names, str):
			names = [names]
		members = sorted(raw_data[0].keys(), key=lambda x: -raw_data[0][x])
		bars = []
		for i, dataset in enumerate(raw_data):
			bars.append(Bar(
				x=map(lambda x: self.members[x][1], members),
				y=map(lambda x: dataset.get(x, 0), members),
				name=names[i]
			))
		layout = Layout(
				title=title,
				margin=Margin(
					l=50,
					r=50,
					b=150,
					t=50,
					pad=4
				),
				barmode=barmode
			)
		return py.plot(Figure(data=Data(bars), layout=layout), filename=self.group['id'] + '-' + str(index), fileopt="overwrite", auto_open=False)

if __name__ == "__main__":
	app.debug = True
	app.run()

