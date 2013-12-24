from flask import Flask, render_template,json,request
import pandas as pd
import numpy as np
import MySQLdb
import pandas.io.sql as psql

from mapping import water_meter_mapping,jplug_mapping,multisensor_mapping

import matplotlib.pyplot as plt
import matplotlib
import json
from mpltools import style
from mpltools import layout

style.use('ggplot')
#s = json.load( open("bmh_matplotlibrc.json") )
#matplotlib.rcParams.update(s)
from threading import Lock
lock = Lock()
import random

import datetime

import pytz

OFFSET=0

TIMEZONE='Asia/Kolkata'

mysql_conn={}
mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor');

smart_meter_data=pd.read_csv('dataset/smart_meter.csv',index_col=0)['W']
ct_data=pd.read_csv('dataset/ct_data_controlled.csv',index_col=0,skipinitialspace=True,names=['id','current'])
light_temp_data=pd.read_csv('dataset/light_temp.csv',index_col=0,names=['node','light','temp'])
jplug_data=pd.read_csv('dataset/jplug.csv',index_col=0,names=['frequency','voltage','real','energy','cost','current','reactive','apparent','pf','phase','jplug_id'])
pir_data=pd.read_csv('dataset/pir.csv',index_col=0,names=['node'])



import random, string

def randomword(length):
	return ''.join(random.choice(string.lowercase) for i in range(length))



def process_smart_meter(data):
	param_string=""
	for param in data['parameters']:
		param_string=param_string+param+","
	query='select timestamp,'+param_string
	query=query[:-1]+' from %s_data where timestamp between %d and %d;' %(data['sensor'],data['start'],data['end'])
	print query
	try:
		result=psql.frame_query(query,mysql_conn[data['sensor']])
	except:
		mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
		mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
		mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
		mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor');
		result=psql.frame_query(query,mysql_conn[data['sensor']])
	result.index=pd.to_datetime(result.timestamp*1e9)
	result=result.drop('timestamp',1)
	freq_downsampled=calculate_downsampling_frequency(result)
	if freq_downsampled is not None:
		result=result.resample(freq_downsampled, how='mean')
		result=result.dropna()
	series=[]
	num_rows=len(result[result.columns[0]].values)
	temp=np.empty((num_rows,2))
	#Subtracting 5.5 hrs to ensure, we always get UTC time
	x=result.index.astype(int)/1e6+5.5*60*60*1000
	temp[:,0]=x
	for key in result:
		temp[:,1]=result[key].values    
		series.append({'name':key,'data':temp.tolist()})
	return json.dumps(series)

def process_water_meter(data):
	series=[]
	for param in data['parameters']:
		query='select timestamp,state from water_data where timestamp between %d and %d and meter_id= %d;' %(data['start'],data['end'],int(param))
		try:
			result=psql.frame_query(query,mysql_conn['water_meter'])
		except Exception, e:
			mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
			mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
			mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
			mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor')
			result=psql.frame_query(query,mysql_conn['water_meter'])
		
		result.index=pd.to_datetime(result.timestamp*1e9)
		result=result.drop('timestamp',1)
		freq_downsampled=calculate_downsampling_frequency(result)
		if freq_downsampled is not None:
			result=result.resample(freq_downsampled, how='max')
			result=result.dropna()
		num_rows=len(result[result.columns[0]].values)
		temp=np.empty((num_rows,2))
		#Subtracting 5.5 hrs to ensure, we always get UTC time
		x=result.index.astype(int)/1e6+5.5*60*60*1000
		temp[:,0]=x
		for key in result:
			temp[:,1]=result[key].values    
			series.append({'name':key+" "+water_meter_mapping[param],'data':temp.tolist()})
	return json.dumps(series)

def process_jplug(data):
	series=[]
	for param in data['parameters']:
		query='select timestamp,active_power from jplug_data where timestamp between %d and %d and mac= "%s";' %(data['start'],data['end'],jplug_mapping[param])
		try:
			result=psql.frame_query(query,mysql_conn['jplug'])
		except:
			mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
			mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
			mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
			mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor')
			result=psql.frame_query(query,mysql_conn['jplug'])
		result.index=pd.to_datetime(result.timestamp*1e9)
		result=result.drop('timestamp',1)
		freq_downsampled=calculate_downsampling_frequency(result)
		if freq_downsampled is not None:
			result=result.resample(freq_downsampled, how='max')
			result=result.dropna()
		num_rows=len(result[result.columns[0]].values)
		temp=np.empty((num_rows,2))
		#Subtracting 5.5 hrs to ensure, we always get UTC time
		x=result.index.astype(int)/1e6+5.5*60*60*1000
		temp[:,0]=x
		for key in result:
			temp[:,1]=result[key].values    
			series.append({'name':key+" "+param,'data':temp.tolist()})
	return json.dumps(series)

def process_multisensor(data):
	series=[]
	for param in data['parameters']:
		query='select timestamp,temp,light from light_temp where timestamp between %d and %d and node_id= %d;' %(data['start'],data['end'],int(param))
		try:
			result=psql.frame_query(query,mysql_conn['multisensor'])
		except:
			mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
			mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
			mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
			mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor')
			result=psql.frame_query(query,mysql_conn['multisensor'])
		result.index=pd.to_datetime(result.timestamp*1e9)
		result=result.drop('timestamp',1)
		freq_downsampled=calculate_downsampling_frequency(result)
		if freq_downsampled is not None:
			result=result.resample(freq_downsampled, how='max')
			result=result.dropna()
		num_rows=len(result[result.columns[0]].values)
		temp=np.empty((num_rows,2))
		#Subtracting 5.5 hrs to ensure, we always get UTC time
		x=result.index.astype(int)/1e6+5.5*60*60*1000
		temp[:,0]=x
		for key in result:
			temp[:,1]=result[key].values    
			series.append({'name':key+" "+multisensor_mapping[param],'data':temp.tolist()})

	return json.dumps(series)



app = Flask(__name__)
  
def calculate_downsampling_frequency(df, threshold_points=15000):
    num_columns=df.columns.size
    num_rows=int(np.sum(df.count()))
    if num_rows>threshold_points:
        factor_in_seconds=int(num_rows/threshold_points)
        print "DOWNSAMPLING: "+str(factor_in_seconds)
        return str(factor_in_seconds)+'s'

    else:
        return None



@app.route('/')
def home():
    return render_template('home.html')
  
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/examples')
def examples():
    return render_template('examples.html')

@app.route('/visualize')
def visualize():
    return render_template('visualize.html')

@app.route('/presentation')
def presentation():
    return render_template('presentation.html')

@app.route('/labeled')
def labeled():
	return render_template('labeled.html')

@app.route('/cite')
def cite():
	return render_template('cite.html')

@app.route('/download')
def download():
	return render_template('download.html')

@app.route('/query',methods=['POST'])
def query():
	data=json.loads(request.data)
	print data
	if data["sensor"]=="smart_meter":
		smart_meter_response=process_smart_meter(data)
		return smart_meter_response
	elif data["sensor"]=="water_meter":
		water_meter_response=process_water_meter(data)
		return water_meter_response
	elif data["sensor"]=="jplug":
		jplug_response=process_jplug(data)
		return jplug_response
	elif data["sensor"]=="multisensor":
		multisensor_response=process_multisensor(data)
		return multisensor_response

@app.route('/labeled_query',methods=['POST'])
def labeled_query():
	no_data=[]
	plt.clf()	
	query_data=json.loads(request.data)
	print query_data
	start_time=query_data["start_time"]
	end_time=query_data["end_time"]
	if query_data["ct_id"] is not None:
		ct_ids=[int(x) for x in query_data["ct_id"]]
	else:
		ct_ids=[]
	if query_data["node_id"] is not None:
		node_ids=[int(x) for x in query_data["node_id"]]
	else: node_ids=[]
	if query_data["jplug_id"] is not None:
		jplug_ids=query_data["jplug_id"]
	else:
		jplug_ids=[]
		
	idx_smart=(smart_meter_data.index>start_time) & (smart_meter_data.index<end_time)
	smart_meter_power=smart_meter_data[idx_smart]
	x_smart_meter=[datetime.datetime.fromtimestamp(x-OFFSET) for x in smart_meter_data.index[idx_smart]]
	y_smart_meter=smart_meter_power.values
	
	count=0
	with lock:
		fig = plt.gcf() # get current figure
		ax1=plt.subplot(1,1,1)
		ax1.set_title('Electricity meter')
		ax1.set_ylabel('Real power (W)')
		ax1.plot(x_smart_meter,y_smart_meter)
		count=1
		
	for ct_id in ct_ids:
		ct_required=ct_data[ct_data.id==ct_id].current
		idx_ct=(ct_required.index>start_time) & (ct_required.index<end_time)
		ct_current=ct_required[idx_ct]
		x_ct=[datetime.datetime.fromtimestamp(x-OFFSET) for x in ct_current.index]
		y_ct=ct_current.values
		if len(y_ct)==0:
			no_data.append("ct%d" %ct_id)
		else:
			with lock:
				n = len(fig.axes) 
				for i in range(n): 
					fig.axes[i].change_geometry(n+1, 1, i+1) 
				ax = fig.add_subplot(n+1, 1, n+1,sharex=ax1) 
				ax.set_title('MCB # %d' %ct_id)
				ax.set_ylabel('Current (A)')
				ax.plot(x_ct,y_ct) 
					
	'''Light'''
	for node_id in node_ids:
		idx_light_temp=(light_temp_data.index>start_time) & (light_temp_data.index<end_time)
		df=light_temp_data[idx_light_temp]
		y_light=df[df["node"]==node_id].light.values
		idx=y_light>0
		y_light=y_light[idx]
		x_light=[datetime.datetime.fromtimestamp(x-OFFSET) for x in df[df["node"]==node_id][idx].index]
	
		if len(y_light)==0:
			no_data.append("light%d" %node_id)
		else:
			with lock:
				n = len(fig.axes) 
				for i in range(n): 
					fig.axes[i].change_geometry(n+1, 1, i+1) 
				ax = fig.add_subplot(n+1, 1, n+1,sharex=ax1) 
				ax.plot(x_light,y_light) 
				ax.set_ylabel('Light')
				ax.set_title('Light node #%d' %node_id)
	'''Temp'''
	for node_id in node_ids:
		y_temp=df[df["node"]==node_id].temp.values
		idx=y_temp>0
		y_temp=y_temp[idx]
		x_temp=[datetime.datetime.fromtimestamp(x-OFFSET) for x in df[df["node"]==node_id][idx].index]
		if len(y_temp)==0:
			no_data.append("temp%d" %node_id)
		else:
			with lock:
				n = len(fig.axes) 
				for i in range(n): 
					fig.axes[i].change_geometry(n+1, 1, i+1) 
				ax = fig.add_subplot(n+1, 1, n+1,sharex=ax1) 
				ax.plot(x_temp,y_temp) 
				ax.set_ylabel('Temperature (F)')
				ax.set_title('Temperature node #%d' %node_id)
			
			
	'''Presence'''
	for node_id in node_ids:
		idx_pir=(pir_data.index>start_time) & (pir_data.index<end_time)
		df_pir=pir_data[idx_pir]
		df_pir=df_pir[df_pir["node"]==node_id]
		y_pir=[1]*len(df_pir.index.values)
		x_pir=[datetime.datetime.fromtimestamp(x-OFFSET) for x in df_pir.index.values]
		if len(x_pir)==0:
			no_data.append("pir%d" %node_id)
		else:
			with lock:
				n = len(fig.axes) 
				for i in range(n): 
					fig.axes[i].change_geometry(n+1, 1, i+1) 
				ax = fig.add_subplot(n+1, 1, n+1,sharex=ax1) 
				ax.plot(x_pir,y_pir,'o')
				ax.set_ylabel('Presence')
				ax.set_title('PIR node #%d' %node_id) 
			
		
	'''jplug'''
	for jplug_id in jplug_ids:
		idx_jplug=(jplug_data.index>start_time) & (jplug_data.index<end_time)
		df=jplug_data[idx_jplug]
		y_jplug=df[df["jplug_id"]==jplug_id]["real"].values
		x_jplug=[datetime.datetime.fromtimestamp(x-OFFSET) for x in df[df["jplug_id"]==jplug_id].index.values]
		if len(y_jplug)==0:
			no_data.append("jplug %s" %jplug_id)
		else:
			with lock:
				n = len(fig.axes) 
				for i in range(n): 
					fig.axes[i].change_geometry(n+1, 1, i+1) 
				ax = fig.add_subplot(n+1, 1, n+1,sharex=ax1) 
				ax.plot(x_jplug,y_jplug)
				ax.set_title('jPlug Power consumption for %s' %jplug_id)
				ax.set_ylabel('Power (W)')
	
		
	with lock:
		filename=randomword(12)+".jpg"
		figure = plt.gcf()
		figure.autofmt_xdate()
		figure.set_size_inches(6,len(fig.axes)*2)	
		
		plt.tight_layout()
		plt.savefig("static/img/temp/"+filename, bbox_inches=0,dpi=100)
		plt.close()
		return json.dumps({"filename":filename,"no_data":no_data})
	

  
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')
