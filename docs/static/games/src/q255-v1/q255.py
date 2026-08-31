"""q255 Vivarium Pact -- infer a social convention whose responses remember fair help."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HABITAT,STRATUM,FAUNA,OFFER,REPLY,FAVOR,CHOICE,BAD=12,10,9,14,6,4,2,11,15
LEVELS=[{"name":"Fair Colony","rule":1,"plan":(1,5)},{"name":"Recent Help","rule":2,"plan":(2,4,1,5,5)},{"name":"Reciprocal Fauna","rule":3,"plan":(1,3,4,2,5,5,5)},{"name":"Temperature Pact","rule":2,"plan":(3,1,4,2,5,5)},{"name":"Remembered Offer","rule":3,"plan":(2,4,1,3,2,5,5,5)},{"name":"Vivarium Pact","rule":1,"plan":(1,4,3,2,4,1,5)}]
def response(rule,a,last,favor):return (rule+a+last+favor)%4
def advance(s,a,x):
 evidence,last,favor,choice=s;evidence=list(evidence)
 if a in (1,2,3):evidence.append((a,response(x["rule"],a,last,favor)));last=a
 elif a==4:favor=(favor+(1 if last in (1,3) else 3))%4
 elif a==5:choice=(choice+1)%4
 return tuple(evidence),last,favor,choice
def target(x):
 s=((),0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HABITAT
  for i in range(3):y=8+i*12;f[y:y+9,8:56]=STRATUM;f[y+2:y+7,12+i*16:20+i*16]=FAUNA-i
  for i,(_,v) in enumerate(g.evidence[-6:]):f[40+i*3:42+i*3,8:11+v*11]=REPLY
  f[37:39,8:20]=OFFER;f[54:57,8:11+g.favor*11]=FAVOR;f[58:60,8:11+g.choice*12]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q255(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q255",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.favor=self.choice=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.evidence,self.last,self.favor,self.choice=advance((self.evidence,self.last,self.favor,self.choice),a,x)
  elif a==6:
   if (self.evidence,self.last,self.favor,self.choice)==self.target and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
