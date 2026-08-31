"""q558 Escapement Lesson -- infer a conditional fault policy from clockwork demonstrations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TOWER,GEAR,WEIGHT,TRACE,CONTEXT,POLICY,GOAL,BAD=1,12,10,14,6,9,11,13,15
LEVELS=[
 {"name":"One Demonstration","seq":(1,)},{"name":"Changed Context","seq":(4,2)},
 {"name":"Ineffective Gesture","seq":(1,3,2)},{"name":"Conditional Policy","seq":(4,1,2,4)},
 {"name":"Fault Contrast","seq":(2,3,4,1,2,1)},
 {"name":"Escapement Lesson","seq":(1,4,2,3,1,2,4,1,2)}]
def advance(s,a):
 context,fault,trace,nuisance,policy=s
 if a==1:trace=trace+((context,(fault+context)%4),);fault=(fault+1+context)%4
 elif a==2:trace=trace+((context,(2*fault+1)%4),);fault=(fault+2-context)%4
 elif a==3:nuisance=(nuisance+1)%4
 elif a==4:context^=1;fault=(fault+context)%4
 elif a==5:policy=(context,fault,trace[-3:],nuisance)
 return context,fault,trace,nuisance,policy
for x in LEVELS:
 s=(0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(4):
   x=8+i*13;f[9:27,x:x+10]=GEAR if i==g.fault else CONTEXT
   f[14:22,x+3:x+7]=WEIGHT
  for i,(c,v) in enumerate(g.trace[-5:]):
   x=8+i*10;f[33:39,x:x+7]=TRACE if c==0 else POLICY;f[40:43,x:x+2+v]=WEIGHT
  f[48:52,8:8+g.context*25+12]=CONTEXT;f[54:58,8:8+g.nuisance*11+6]=TRACE
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q558(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q558",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.fault=self.nuisance=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.fault,self.trace,self.nuisance,self.policy=advance((self.context,self.fault,self.trace,self.nuisance,self.policy),a)
  elif a==6:
   if (self.context,self.fault,self.trace,self.nuisance,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
