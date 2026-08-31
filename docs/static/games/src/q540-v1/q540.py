"""q540 Spore Lesson -- infer a policy and coordinate unequal autonomous schedules."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,SPORE,HUMID,CLOCK,COORD,GESTURE,BAD=2,8,12,6,4,9,13,11,15
LEVELS=[{"name":"Twin Schedule","cycles":(2,2),"context":0},{"name":"Unequal Schedule","cycles":(2,3),"context":0},{"name":"Context Shift","cycles":(3,3),"context":1},{"name":"Sparse Meeting","cycles":(3,4),"context":1},{"name":"Long Meeting","cycles":(4,5),"context":0},{"name":"Spore Lesson","cycles":(5,6),"context":1}]
for x in LEVELS:
 x["plan"]=(4,)*x["context"]+(1,)*x["cycles"][0]+(2,)*x["cycles"][1]+(3,);x["demo"]=(4,)*x["context"]+(1,5)+(1,)*(x["cycles"][0]-1)+(2,)*x["cycles"][1]+(3,)
def advance(s,a,x):
 policy,context,clocks,spores,coordinated,gesture=s;clocks=list(clocks)
 if a==1:policy=(policy+context+1)%4;clocks[0]=(clocks[0]+1)%x["cycles"][0]
 elif a==2:clocks[1]=(clocks[1]+1)%x["cycles"][1]
 elif a==3:
  if tuple(clocks)!=(0,0):return None
  spores=(spores+policy+context+1)%7;coordinated=(policy,context,tuple(clocks),spores)
 elif a==4:context^=1
 elif a==5:gesture+=1
 return policy,context,tuple(clocks),spores,coordinated,gesture
def target(x):
 s=(0,0,(0,0),0,None,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE;f[8:32,7:29]=GLASS;f[8:32,35:57]=GLASS
  for i,a in enumerate(g.cfg["demo"]):f[11:15,9+i*4:12+i*4]=(a+5)%16
  f[38:42,8:8+g.clocks[0]*8]=CLOCK;f[44:48,8:8+g.clocks[1]*7]=CLOCK+2;f[51:54,8:12+g.policy*10]=HUMID
  if g.coordinated:f[55:59,39:56]=COORD
  if g.gesture:f[34:37,42:56]=GESTURE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q540(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q540",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.policy=self.context=0;self.clocks=(0,0);self.spores=0;self.coordinated=None;self.gesture=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.policy,self.context,self.clocks,self.spores,self.coordinated,self.gesture),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.policy,self.context,self.clocks,self.spores,self.coordinated,self.gesture=s
  elif a==6:
   if (self.policy,self.context,self.clocks,self.spores,self.coordinated,self.gesture)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
