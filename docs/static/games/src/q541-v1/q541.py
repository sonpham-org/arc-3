"""q541 Tapestry Lesson -- infer a conditional weaving policy through a topology rewire."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,SHUTTLE,THREAD,DEMO,CONTEXT,REWIRE,GOAL,BAD=1,8,14,10,6,12,11,13,15
LEVELS=[
 {"name":"One Example","seq":(1,)},{"name":"Context Thread","seq":(4,2)},
 {"name":"Null Gesture","seq":(1,3,2)},{"name":"Completed Pattern","seq":(1,2,4,1)},
 {"name":"Rewired Loom","seq":(2,1,3,4,2,1)},
 {"name":"Tapestry Lesson","seq":(1,4,2,3,1,2,4,2,1)}]
def advance(s,a):
 context,shuttle,weave,trace,rewired,policy=s
 if a==1:shuttle=(shuttle+1+context)%6;weave=(weave+shuttle)%5;trace=trace+((context,1,shuttle),)
 elif a==2:shuttle=(shuttle+2+rewired)%6;weave=(2*weave+context)%5;trace=trace+((context,2,shuttle),)
 elif a==3:trace=trace+((context,0,shuttle),)
 elif a==4:context^=1;rewired=(rewired+int(weave>=2)+context)%3
 elif a==5:policy=(context,shuttle,weave,trace[-4:],rewired)
 return context,shuttle,weave,trace,rewired,policy
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOOM
  for i in range(6):
   x=8+i*8;f[8:31,x:x+5]=THREAD;f[11+((i+g.rewired)%3)*6:16+((i+g.rewired)%3)*6,x:x+7]=SHUTTLE if i==g.shuttle else CONTEXT
  for i,(_,a,v) in enumerate(g.trace[-6:]):f[36:41,8+i*8:14+i*8]=DEMO if a else REWIRE;f[42:44,8+i*8:10+i*8+v]=THREAD
  f[49:53,8:8+g.weave*9+6]=CONTEXT;f[55:59,8:8+g.rewired*15+10]=REWIRE
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q541(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q541",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.shuttle=self.weave=self.rewired=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.shuttle,self.weave,self.trace,self.rewired,self.policy=advance((self.context,self.shuttle,self.weave,self.trace,self.rewired,self.policy),a)
  elif a==6:
   if (self.context,self.shuttle,self.weave,self.trace,self.rewired,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
