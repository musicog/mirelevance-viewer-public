from flask import Flask, render_template, request
#from flask_login import LoginManager, UserMixin, login_required, login_user, current_user
from flask_socketio import SocketIO, emit
import json
import operator
import sqlite3
import os
from pprint import pprint

def prefix_route(route_function, prefix='', mask='{0}{1}'):
  '''
    Defines a new route function with a prefix.
    The mask argument is a `format string` formatted with, in that order:
      prefix, route
  '''
  def newroute(route, *args, **kwargs):
    '''New function to prefix the route'''
    return route_function(mask.format(prefix, route), *args, **kwargs)
  return newroute

app = Flask(__name__, static_url_path="/relevance-static")
app.route = prefix_route(app.route, '/relevance')
app.debug = False
app.config["SECRET_KEY"] = os.environ.get("MIRELEVANCESECRET") or 'asdfasdgafsgfadwsxcbget4r3qwasdft'
app.config["SQLITEDB"] = os.environ.get("MIRELEVANCEDB") or "relevance-public.db"

socketio = SocketIO(app, path="/relevance-socketio", cors_allowed_origins='*')

db = sqlite3.connect(app.config["SQLITEDB"])


@app.route('/')
def index():
    return render_template("index-public.html")


@app.route('/heatmap')
def heatmap():
        return render_template("index-public.html") 

@app.route('/query')
def query():
        response = app.make_response(render_template("query.html"))
        return response

def extractStratCompIds(tup):
    return tup[0].replace("stratComp", "")

@app.route('/queryFindings')
def queryFindings():
    tupleID = request.args["tupleID"]
    print(("Got :", tupleID))
    findingIDs = request.args["findings"].split("_")
    print("Findings :")
    pprint(findingIDs)
    c = db.cursor()
    findingsDetailsQuery = """
        select f.id, f.description, s.id, s.description, s.methodology, s.sampleframe, s.samplesize, s.limitations, s.comments, s.reliability, a.title, a.authors, a.journal, a.year, a.id
        from findings f 
        join studies s on f.studyid = s.id
        join articles a on s.articleid = a.id
        WHERE f.id IN ("""
    # add as many placeholders for the "WHERE f.id IN" clause as there are finding ids
    findingsDetailsQuery += ",".join(["?"]*len(findingIDs)) + ");"
    findings = list()
    for row in c.execute(findingsDetailsQuery, findingIDs):
        findings.append({ 
            "findingid": row[0],
            "f.description": row[1],
            "s.id": row[2],
            "s.description": row[3],
            "s.methodology": row[4],
            "s.samplesize": row[5],
            "s.sampleframe": row[6],
          # "s.limitations": row[7],
          # "s.comments": row[8],
          # "s.reliability": row[9],
            "a.title": row[10],
            "a.authors": row[11],
            "a.journal": row[12],
            "a.year": row[13],
	    "a.id": row[14]})
    return json.dumps({
        "tupleID": tupleID,
        "findings": findings
    });

@app.route('/querySubmit')
def querySubmit():
    findings = list();
    findingStratComps = dict();
    c = db.cursor()
    stratCompIds = list(map(extractStratCompIds, list(request.args.items())))
    findingsByStratCompsQuery = ""
    for ix, scId in enumerate(stratCompIds):
        findingsByStratCompsQuery += "SELECT fi.findingid FROM findingInstances fi WHERE fi.stratCompId = ?"
        if ix < len(stratCompIds)-1:
            findingsByStratCompsQuery += " INTERSECT "
    for row in c.execute(findingsByStratCompsQuery, stratCompIds):
        findings.append(row[0])
    print(findings)
    # now build the query that fetches us strat descriptors for all the findings we've retrieved
    stratDescQuery = """
        select f.id, f.studyid, sc.id, sc.stratum, sc.description, sc.hint
        from findings f 
        join findingInstances fi on f.id = fi.findingid
        join stratumComponents sc on fi.stratcompid = sc.id
        WHERE f.id IN ("""
    # add as many placeholders for the "WHERE f.id IN" clause as there are finding ids
    stratDescQuery += ",".join(["?"]*len(findings)) + ");"
    for row in c.execute(stratDescQuery, findings):
        if row[0] not in findingStratComps: # first time seeing this findingid, set up list
            findingStratComps[row[0]] = list()
        # now fill in this stratum component
        findingStratComps[row[0]].append ({
                "studyid": row[1],
                "stratCompID": row[2],
                "stratum": row[3],
                "description":row[4],
                "hint": row[5]})

    # now reshape data so we have a dictionary of stratDesc tuples linked to findings
    stratDescTuples = dict()
    for findingid, fSC in findingStratComps.items():
        thisFindingStratComps = list()
        for sC in fSC:
            thisFindingStratComps.append(sC["stratCompID"])
        thisTuple = tuple(sorted(thisFindingStratComps))
        if thisTuple not in stratDescTuples:
            stratDescTuples[thisTuple] = {"tupleID": thisTuple, "studyids": set(), "freq":0, "findings": list(), "stratComps": list()}
            for sC in fSC:
                stratDescTuples[thisTuple]["stratComps"].append({
                    "stratum": sC["stratum"],
                    "description": sC["description"],
                    "hint": sC["hint"]})
        stratDescTuples[thisTuple]["freq"] += 1;
        stratDescTuples[thisTuple]["findings"].append(findingid)
        stratDescTuples[thisTuple]["studyids"].add(fSC[0]["studyid"])
    
    for tup in stratDescTuples:
        stratDescTuples[tup]["numStudies"] = len(stratDescTuples[tup]["studyids"])
        del stratDescTuples[tup]["studyids"]
    stratDescTuplesByFreq = sorted(list(stratDescTuples.items()), key=lambda k_v:(k_v[1]["numStudies"], k_v[1]["freq"],k_v[0]), reverse=True)

    # finally, send the whole shebang to the client
    return json.dumps(stratDescTuplesByFreq)
    

@socketio.on('clientConnectionEvent')
def socket_connect(message):
    print(message)

@socketio.on('stratCompRequest')
def handle_stratCompRequest(message):
    stratA = message[0]
    stratB = message[1]
    c = db.cursor()
    findingsByStratQuery = """
        select f.id from findings f join findingInstances fi on f.id = fi.findingid join stratumComponents sc on fi.stratcompid = sc.id where sc.stratum = ? 
        INTERSECT
        select f.id from findings f join findingInstances fi on f.id = fi.findingid join stratumComponents sc on fi.stratcompid = sc.id where sc.stratum = ?; 
        """
    findings = list();
    findingStratComps = dict();
    for row in c.execute(findingsByStratQuery, (stratA, stratB)):
        findings.append(row[0])
    # now build the query that fetches us strat descriptors for all the findings we've retrieved
    stratDescQuery = """
        select f.id, f.studyid, sc.id, sc.stratum, sc.description, sc.hint
        from findings f 
        join findingInstances fi on f.id = fi.findingid
        join stratumComponents sc on fi.stratcompid = sc.id
        WHERE f.id IN ("""
    # add as many placeholders for the "WHERE f.id IN" clause as there are finding ids
    stratDescQuery += ",".join(["?"]*len(findings)) + ");"
    for row in c.execute(stratDescQuery, findings):
        if row[0] not in findingStratComps: # first time seeing this findingid, set up list
            findingStratComps[row[0]] = list()
        # now fill in this stratum component
        findingStratComps[row[0]].append ({
                "studyid": row[1],
                "stratCompID": row[2],
                "stratum": row[3],
                "description":row[4],
                "hint": row[5]})

    # now reshape data so we have a dictionary of stratDesc tuples linked to findings
    stratDescTuples = dict()
    for findingid, fSC in findingStratComps.items():
        thisFindingStratComps = list()
        for sC in fSC:
            thisFindingStratComps.append(sC["stratCompID"])
        thisTuple = tuple(sorted(thisFindingStratComps))
        if thisTuple not in stratDescTuples:
            stratDescTuples[thisTuple] = {"tupleID": thisTuple, "studyids": set(), "freq":0, "findings": list(), "stratComps": list()}
            for sC in fSC:
                stratDescTuples[thisTuple]["stratComps"].append({
                    "stratum": sC["stratum"],
                    "description": sC["description"],
                    "hint": sC["hint"]})
        stratDescTuples[thisTuple]["freq"] += 1;
        stratDescTuples[thisTuple]["findings"].append(findingid)
        stratDescTuples[thisTuple]["studyids"].add(fSC[0]["studyid"])
    
    for tup in stratDescTuples:
        stratDescTuples[tup]["numStudies"] = len(stratDescTuples[tup]["studyids"])
        del stratDescTuples[tup]["studyids"]
    stratDescTuplesByFreq = sorted(list(stratDescTuples.items()), key=lambda k_v1:(k_v1[1]["numStudies"], k_v1[1]["freq"],k_v1[0]), reverse=True)

    # finally, send the whole shebang to the client
    emit('stratCompRequestHandled', stratDescTuplesByFreq)
   
                
@socketio.on('showFindingsRequest')
def handle_showFindingsRequest(message):
    print(message)
    tupleID = message["tupleID"]
    findingIDs = message["findings"]
    c = db.cursor()
    findingsDetailsQuery = """
        select f.id, f.description, s.id, s.description, s.methodology, s.sampleframe, s.samplesize, s.limitations, s.comments, s.reliability, a.title, a.authors, a.journal, a.year, a.id
        from findings f 
        join studies s on f.studyid = s.id
        join articles a on s.articleid = a.id
        WHERE f.id IN ("""
    # add as many placeholders for the "WHERE f.id IN" clause as there are finding ids
    findingsDetailsQuery += ",".join(["?"]*len(findingIDs)) + ");"
    findings = list()
    for row in c.execute(findingsDetailsQuery, findingIDs):
        findings.append({ 
            "findingid": row[0],
            "f.description": row[1],
            "s.id": row[2],
            "s.description": row[3],
            "s.methodology": row[4],
            "s.samplesize": row[5],
            "s.sampleframe": row[6],
          # "s.limitations": row[7],
          # "s.comments": row[8],
          # "s.reliability": row[9],
            "a.title": row[10],
            "a.authors": row[11],
            "a.journal": row[12],
            "a.year": row[13],
	    "a.id": row[14]})
    emit("showFindingsRequestHandled", {
        "tupleID": tupleID,
        "findings": findings});

        

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0")
    app.debug = False 
