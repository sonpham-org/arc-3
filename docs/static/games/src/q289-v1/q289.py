"""q289 Monsoon Probe -- distinguish weather causes before a joint-cycle repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,PROBE,EVIDENCE,CYCLE,REPAIR,BAD=2,10,9,14,6,4,11,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Direct Rain","model":1,"periods":(2,2),"plan":(1,4,5)},{"name":"Shared Cloud","model":2,"periods":(3,3),"plan":(2,1,4,5)},{"name":"Coincident Drops","model":3,"periods":(2,4),"plan":(1,3,2,4,5)},{"name":"Unequal Weather","model":2,"periods":(2,3),"plan":(2,4,3,1,2,4,5)},{"name":"Long Diagnosis","model":3,"periods":(3,4),"plan":routine(12)},{"name":"Monsoon Probe","model":1,"periods":(4,5),"plan":routine(20)}]
def advance(s,a,x):
 evidence,pa,pb,diagnostic,repair=s;evidence=list(evidence)
 if repair is not None:return None
 if a in (1,2,3,4):
  if a==4:diagnostic=(x["model"],pa,pb)
  else:evidence.append((a,(x["model"]*a+pa+2*pb)%5))
  pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or diagnostic is None or not evidence:return None
  repair=(x["model"],tuple(evidence),diagnostic)
 return tuple(evidence),pa,pb,diagnostic,repair
def target(x):
 s=((),0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(3):x=8+i*18;f[8:30,x:x+14]=CLOUD;f[13+i*4:19+i*4,x+4:x+10]=RAIN-i
  for i,(_,v) in enumerate(g.evidence[-6:]):f[34+i*3:36+i*3,8:11+v*10]=EVIDENCE
  f[53:56,8:24]=CYCLE if g.diagnostic else PROBE;f[57:60,40:56]=REPAIR if g.repair else CLOUD
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q289(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q289",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.pa=self.pb=0;self.diagnostic=self.repair=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.pa,self.pb,self.diagnostic,self.repair),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.evidence,self.pa,self.pb,self.diagnostic,self.repair=s
  elif a==6:
   if (self.evidence,self.pa,self.pb,self.diagnostic,self.repair)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
