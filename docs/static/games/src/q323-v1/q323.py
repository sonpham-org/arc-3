"""q323 Ember Survey -- buy bounded heat evidence from the same fuel used to move and commit."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,LENS,EVIDENCE,RESOURCE,COMMIT,BAD=15,9,8,14,10,6,11,7,2
LEVELS=[{"name":"One Heat Slice","fuel":3,"plan":(1,5)},{"name":"Moved Sounding","fuel":5,"plan":(2,4,1,5)},{"name":"Evidence Union","fuel":6,"plan":(1,3,4,2,5)},{"name":"Fuel Tradeoff","fuel":7,"plan":(2,4,3,1,5)},{"name":"Distinct Bands","fuel":8,"plan":(3,1,4,2,3,5)},{"name":"Ember Survey","fuel":10,"plan":(1,4,3,2,4,1,5)}]
def advance(s,a):
 heat,evidence,resource,committed=s;evidence=list(evidence)
 if resource<=0 or committed>=0:return None
 if a in (1,2,3):evidence.append((a,heat,(a+heat+resource)%4))
 elif a==4:heat=(heat+1)%4
 elif a==5:committed=(sum(v for _,_,v in evidence)+heat)%4
 resource-=1
 return heat,tuple(evidence),resource,committed
def target(x):
 s=(0,(),x["fuel"],-1)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:14,8:56]=HEAT
  for i in range(3):x=9+i*18;f[19:34,x:x+12]=LENS;f[24:29,x+4:x+8]=VESSEL-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[38+i*3:40+i*3,8:11+v*11]=EVIDENCE
  f[54:57,8:11+g.resource*4]=RESOURCE;f[58:60,8:20]=COMMIT if g.committed>=0 else HEAT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q323(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q323",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.heat=0;self.evidence=();self.resource=x["fuel"];self.committed=-1
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.heat,self.evidence,self.resource,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.heat,self.evidence,self.resource,self.committed=s
  elif a==6:
   if (self.heat,self.evidence,self.resource,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
