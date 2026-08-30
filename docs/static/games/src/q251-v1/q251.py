"""q251 Pollen Pact -- infer a social convention whose response complements after wear."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,KITE,OFFER,RESPONSE,WEAR,CHOICE,PACT,BAD=10,14,7,12,15,8,9,11,13
LEVELS=[
 {"name":"Fair Bloom","rule":1,"before":(1,),"after":(2,)},
 {"name":"Recent Pollen","rule":2,"before":(2,1),"after":(3,)},
 {"name":"Reciprocal Kite","rule":3,"before":(1,3),"after":(2,1)},
 {"name":"Visible Wear","rule":2,"before":(3,2,1),"after":(1,3)},
 {"name":"Complement Pact","rule":3,"before":(2,1,3),"after":(3,1,2)},
 {"name":"Pollen Pact","rule":1,"before":(1,2,3,1),"after":(2,3,1,2)}]
def response(rule,offer,last,worn):
 v=(rule+offer+last)%4
 return 3-v if worn else v
def expected(x):
 out=[];last=0
 for a in x["before"]:out.append((a,response(x["rule"],a,last,False)));last=a
 for a in x["after"]:out.append((a,response(x["rule"],a,last,True)));last=a
 return tuple(out)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[7:57,4:60]=MEADOW
  for i in range(3):px=9+i*18;f[11:20,px:px+10]=KITE;f[20:39,px+4:px+7]=OFFER
  for i,(_,v) in enumerate(g.evidence[-8:]):f[42+i*2:44+i*2,7:7+v*12]=RESPONSE
  if g.worn:f[6:10,8:56]=WEAR
  f[54:56,8:8+x["rule"]*13]=PACT;f[57:60,8:8+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q251(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.evidence=[];self.last=0;self.worn=False;self.choice=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q251",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=[];self.last=0;self.worn=False;self.choice=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.evidence.append((a,response(x["rule"],a,self.last,self.worn)));self.last=a
  elif a==4:self.worn=True
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==expected(x) and self.worn and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
