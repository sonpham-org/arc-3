"""q349 Monsoon Survey -- spend evidence only where two weather cycles align."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,LENS,EVIDENCE,CYCLE,POLICY,BAD=4,10,9,14,6,11,5,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Paired Sample","periods":(2,2),"budget":2,"plan":routine(2)},{"name":"Triple Sample","periods":(3,3),"budget":3,"plan":routine(3)},{"name":"Nested Survey","periods":(2,4),"budget":3,"plan":routine(4)},{"name":"Unequal Evidence","periods":(2,3),"budget":5,"plan":routine(6)},{"name":"Long Allocation","periods":(3,4),"budget":9,"plan":routine(12)},{"name":"Monsoon Survey","periods":(4,5),"budget":15,"plan":routine(20)}]
def advance(s,a,x):
 evidence,cost,pa,pb,policy=s;evidence=list(evidence)
 if a in (1,2,3,4):
  if a in (1,2,3):
   item=(a,pa,pb,(a+pa+2*pb)%5);cost+=2 if item in evidence else 1;evidence.append(item)
  pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or not evidence or cost>x["budget"]:return None
  policy=(sum(v for *_,v in evidence)+cost)%5
 return tuple(evidence),cost,pa,pb,policy
def target(x):
 s=((),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(3):x=8+i*18;f[8:30,x:x+14]=LENS;f[13+i*4:19+i*4,x+4:x+10]=RAIN-i
  for i,(*_,v) in enumerate(g.evidence[-6:]):f[34+i*3:36+i*3,8:11+v*9]=EVIDENCE
  f[53:56,8:24]=CYCLE;f[57:60,8:11+g.policy*10]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q349(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q349",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.cost=self.pa=self.pb=self.policy=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.cost,self.pa,self.pb,self.policy),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.cost,self.pa,self.pb,self.policy=s
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.evidence,self.cost,self.pa,self.pb,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
