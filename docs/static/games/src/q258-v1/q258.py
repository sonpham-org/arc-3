"""q258 Escapement Pact -- infer a convention using a fault-separating gear intervention."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,OFFER,REPLY,DIAG,CHOICE,BAD=1,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Fair Weight","rule":1,"fault":1,"plan":(1,4,5)},{"name":"Recent Gear","rule":2,"fault":2,"plan":(2,4,1,5,5)},{"name":"Reciprocal Tick","rule":3,"fault":3,"plan":(1,3,4,2,5,5,5)},{"name":"Diagnostic Pact","rule":2,"fault":2,"plan":(3,1,4,2,5,5)},{"name":"Fault Courtesy","rule":3,"fault":3,"plan":(2,4,1,3,2,5,5,5)},{"name":"Escapement Pact","rule":1,"fault":1,"plan":(1,4,3,2,4,1,5)}]
def response(rule,a,last,phase,fault):return (rule*a+last+phase+fault)%4
def advance(s,a,x):
 evidence,last,phase,diagnostic,choice=s;evidence=list(evidence)
 if a in (1,2,3):evidence.append((a,response(x["rule"],a,last,phase,x["fault"])));last=a
 elif a==4:diagnostic=(x["fault"],(last+x["fault"]+phase)%4);phase=(phase+1)%4
 elif a==5:choice=(choice+1)%4
 return tuple(evidence),last,phase,diagnostic,choice
def target(x):
 s=((),0,0,None,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(3):x=8+i*18;f[9:32,x:x+14]=GEAR;f[15+i*4:22+i*4,x+4:x+10]=WEIGHT-i
  for i,(_,v) in enumerate(g.evidence[-6:]):f[36+i*3:38+i*3,8:11+v*11]=REPLY
  f[33:35,8:20]=OFFER;f[53:56,8:20]=DIAG if g.diagnostic else GEAR;f[57:60,8:11+g.choice*12]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q258(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q258",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.last=self.phase=self.choice=0;self.diagnostic=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.evidence,self.last,self.phase,self.diagnostic,self.choice=advance((self.evidence,self.last,self.phase,self.diagnostic,self.choice),a,x)
  elif a==6:
   if (self.evidence,self.last,self.phase,self.diagnostic,self.choice)==self.target and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
