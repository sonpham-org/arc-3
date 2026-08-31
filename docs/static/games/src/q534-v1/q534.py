"""q534 Honeycomb Lesson -- infer a two-clock courier policy from contextual demonstrations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,SCENT,DEMO,CLOCK,GOAL,BAD=1,9,11,14,10,6,12,13,15
LEVELS=[
 {"name":"One Courier","seq":(1,)},{"name":"Context Scent","seq":(4,2)},
 {"name":"Null Dance","seq":(1,3,2)},{"name":"Outer Clock","seq":(1,2,4,1)},
 {"name":"Layered Policy","seq":(2,1,3,4,2,1)},
 {"name":"Honeycomb Lesson","seq":(1,4,2,3,1,2,4,2,1)}]
def advance(s,a):
 context,courier,local,outer,trace,policy=s
 if a==1:courier=(courier+1+context)%7;local=(local+1)%3;trace=trace+((context,1,courier),)
 elif a==2:courier=(courier+2+outer)%7;local=(local+2)%3;trace=trace+((context,2,courier),)
 elif a==3:trace=trace+((context,0,courier),)
 elif a==4:context^=1;outer=(outer+int(local==0)+context)%4
 elif a==5:policy=(context,courier,local,outer,trace[-4:])
 if a in (1,2) and local==0:outer=(outer+1)%4
 return context,courier,local,outer,trace,policy
for x in LEVELS:
 s=(0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=APIARY
  for i in range(12):
   x=8+(i%6)*8;y=8+(i//6)*14;f[y:y+10,x:x+6]=CELL;f[y+3:y+7,x+2:x+5]=COURIER if i==g.courier else SCENT
  for i,(_,a,v) in enumerate(g.trace[-5:]):x=8+i*10;f[38:43,x:x+7]=DEMO if a else SCENT;f[44:46,x:x+2+v]=COURIER
  f[49:53,8:8+g.local*15+10]=CLOCK;f[55:59,8:8+g.outer*11+7]=SCENT
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q534(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q534",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.courier=self.local=self.outer=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.courier,self.local,self.outer,self.trace,self.policy=advance((self.context,self.courier,self.local,self.outer,self.trace,self.policy),a)
  elif a==6:
   if (self.context,self.courier,self.local,self.outer,self.trace,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
