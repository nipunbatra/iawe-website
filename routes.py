from flask import Flask, render_template,json,request
import pandas as pd
import numpy as np
import MySQLdb
import pandas.io.sql as psql

from mapping import water_meter_mapping,jplug_mapping,multisensor_mapping

import prettyplotlib as ppl

# prettyplotlib imports 
from prettyplotlib import plt
from prettyplotlib import mpl
from prettyplotlib import brewer2mpl

from threading import Lock
lock = Lock()
import random

mysql_conn={}
mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');
mysql_conn['jplug']=MySQLdb.connect(user='root',passwd='password',db='jplug');
mysql_conn['water_meter']=MySQLdb.connect(user='root',passwd='password',db='water_meter');
mysql_conn['multisensor']=MySQLdb.connect(user='root',passwd='password',db='multisensor');

smart_meter_data=pd.read_csv('../dataset/smart_meter.csv',index_col=0)['W']
ct_data=pd.read_csv('../dataset/ct_data_controlled.csv',index_col=0,skipinitialspace=True,names=['id','current'])
light_temp_data=pd.read_csv('../dataset/light_temp.csv',index_col=0,names=['node','light','temp'])
jplug_data=pd.read_csv('../dataset/jplug.csv',index_col=0,names=['frequency','voltage','real','energy','cost','current','reactive','apparent','pf','phase','jplug_id'])
pir_data=pd.read_csv('../dataset/pir.csv',index_col=0,names=['node'])



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

@app.route('/visualize')
def visualize():
    return render_template('visualize.html')

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

	

  
if __name__ == '__main__':
    app.run(debug=True)
