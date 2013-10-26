

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
		result=psql.frame_query(query,mysql_conn[data['water_meter']])
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
			series.append({'name':key,'data':temp.tolist()})
	return json.dumps(series)