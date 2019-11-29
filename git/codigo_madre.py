from flask import Flask, request, render_template, redirect
import re
import urllib
import numpy as np
import time
from elasticsearch import Elasticsearch

resultados=np.zeros(100)
resultados_umbral=np.zeros(100)
fechas_umbral=[None]*100
horas_umbral=[None]*100

es=Elasticsearch("http://localhost:9200")

def valor():
	with urllib.request.urlopen('https://quotes.wsj.com/index/DJIA/') as response:
		html = response.read()
	valor=re.search(r'(<span id="quote_val">)\d+[.]\d\d',str(html)).group(0)
	#valor=valor[21:len(valor)]
	return valor[21:len(valor)]
def hora():
	with urllib.request.urlopen('https://quotes.wsj.com/index/DJIA/') as response:
		html = response.read()	
	hora=re.search(r'(?P<hora>\d+[:]\d\d (PM))',str(html))
	if hora is None:
		hora=re.search(r'(?P<hora>\d+[:]\d\d (AM))',str(html)).group('hora')
	else:
		hora=hora.group('hora')
	hora=hora[0:len(hora)-3]
		
	return hora
def fecha():
	with urllib.request.urlopen('https://quotes.wsj.com/index/DJIA/') as response:
		html = response.read()
	fecha=re.search(r'(?P<fecha>(EST) \d+(/)\d+(/)\d\d)',str(html)).group('fecha')
	return fecha[4:len(fecha)]
app = Flask(__name__)

@app.route('/')
def my_form():

	datos={"valor":valor(),"fecha":fecha(),"hora":hora()}
	#Mirar la longitud de la base para añadir el valor recogido en la posicion longitud+1 de la base local
	res_search=es.search(index="djia",body={"query":{"match_all":{}}})
	num_id=res_search['hits']['total']
	#Añadir a los indices de la base local
	es.index(index="djia", doc_type="DJIA",id=num_id+1,body={'valor':datos['valor']})
	es.index(index="fecha", doc_type="DJIA",id=num_id+1,body={'fecha':datos['fecha']})
	es.index(index="hora", doc_type="DJIA",id=num_id+1,body={'hora':datos['hora']})
	#res=es.get(index="base_local",doc_type="DJIA",id=num_id+1)

	#Añadir valor recogido en la base remota
	urllib.request.urlopen("https://api.thingspeak.com/update?api_key=RVOY0BPCJVWWDTVG&field1="+str(datos['valor']))
	urllib.request.urlopen("https://api.thingspeak.com/update?api_key=RVOY0BPCJVWWDTVG&field2="+str(datos['fecha']))
	urllib.request.urlopen("https://api.thingspeak.com/update?api_key=RVOY0BPCJVWWDTVG&field3="+str(datos['hora']))
	#return render_template('pagina_web.html',numero_DJIA=res['_source']['valor'],  numero_base=num_id, media_de_DJI=media) #numero=res['_source']['valor']) 
	return render_template('pagina_web.html',numero_DJIA=float(datos['valor']),hora=datos['hora'],fecha=datos['fecha'],  numero_base=num_id+1)

@app.route('/umbral',methods=['POST'])
def umbral():
	i=1;
	cont=0;
	res_search=es.search(index="djia",body={"query":{"match_all":{}}})
	num_id=len(res_search['hits']['hits'])
	umbral=request.form['umbral'] #umbral obtenido por el metodo post
	while i<=num_id:
		res_aux=es.get(index="djia",doc_type="DJIA",id=i)
		resultado=res_aux['_source']['valor']

		res_aux=es.get(index="fecha",doc_type="DJIA",id=i)
		fecha=res_aux['_source']['fecha']

		res_aux=es.get(index="hora",doc_type="DJIA",id=i)
		hora=res_aux['_source']['hora']
		if float(resultado) > float(umbral):
			resultados_umbral[cont]=float(resultado)
			fechas_umbral[cont]=fecha
			horas_umbral[cont]=hora
			cont=cont+1
		i=i+1
	#Pasar el array a lista y luego ordenarla de mayor a menor
	resultados_umbral.tolist()
	resultados_umbral_sorted=sorted(resultados_umbral,reverse=True)
	
	return render_template('umbral.html', len=5,resultados=resultados_umbral_sorted,fechas=fechas_umbral,horas=horas_umbral)
@app.route('/media',methods=['POST'])
def media():
	es=Elasticsearch("http://localhost:9200")
	res=es.get(index="flag",doc_type="flag",id=1)
	res_aux=float(res['_source']['base'])
	if res_aux==1: 
		res_search=es.search(index="djia",body={"query":{"match_all":{}}})
		num_id=len(res_search['hits']['hits'])
		i=1;
		media=1;
		while i<=num_id:
			resultado=es.get(index="djia",doc_type="DJIA",id=i)
			resultados[i]=float(resultado['_source']['valor'])
			print(resultados[i])
			i=i+1
		media=np.mean(resultados[1:num_id])
		es.index(index="flag", doc_type="flag",id=1,body={'base':0})
		base='local'
	else:
		string="daily"
		media_link=urllib.request.urlopen("https://api.thingspeak.com/channels/919973/fields/1.json?results=100&average="+string).read()
		media=re.search(r'(")\d+[.]\d+("}]})',str(media_link)).group(0)
		media=media[1:len(media)-4]
		es.index(index="flag", doc_type="flag",id=1,body={'base':1})
		base='remota'

	return render_template('media.html',media_de_DJIA=media,base=base)
@app.route('/grafica',methods=['POST'])
def grafica():
	return redirect("https://thingspeak.com/channels/919973")
if __name__ == '__main__': 
	app.debug=True
	app.run(host='0.0.0.0')

	