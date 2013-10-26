from flask import Flask, render_template,json,request
import pandas as pd
import numpy as np
import MySQLdb
import pandas.io.sql as psql
mysql_conn={}
mysql_conn['smart_meter']=MySQLdb.connect(user='root',passwd='password',db='smart_meter');


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
	

  
if __name__ == '__main__':
    app.run(debug=True)
