"""q414 Honeycomb Revision -- recalibrate a worn scent law across two clocks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,WEAR,RULE,LOCAL,GLOBAL,BAD=12,9,14,5,11,4,6,7,15
LEVELS=[{"name":"Old Scent","cycle":2,"boundary":3,"mode":1,"plan":(1,2,5)},{"name":"Wear Cell","cycle":2,"boundary":2,"mode":2,"plan":(2,1,4,5)},{"name":"Delayed Nectar","cycle":3,"boundary":2,"mode":3,"plan":(3,2,1,5)},{"name":"Two-Clock Law","cycle":3,"boundary":3,"mode":2,"plan":(1,4,2,3,5)},{"name":"Nested Revision","cycle":4,"boundary":2,"mode":1,"plan":(2,3,4,1,2,5)},{"name":"Honeycomb Revision","cycle":4,"boundary":3,"mode":3,"plan":(3,1,4,2,3,1,5)}]
def advance(s,a,x):
 couriers,wear,local,global_,delay=s;couriers=list(couriers)
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:couriers[i]=(couriers[i]+a+global_)%4
  elif rule==2:couriers[i]=3-couriers[i]
  else:delay=(delay+a+i+global_)%4
  wear+=1
 elif a==4:delay=(delay+local+global_)%4
 elif a==5:couriers=[(v+delay+global_)%4 for v in couriers];delay=0
 local+=1
 if local>=x["cycle"]:local=0;global_=(global_+1)%4
 return tuple(couriers),wear,local,global_,delay
def target(x):
 s=((0,1,2),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=APIARY;f[8:15,8:56]=CELL
  for i,v in enumerate(g.couriers):x=9+i*18;f[20:37,x:x+12]=COURIER+i;f[24+v*3:29+v*3,x+3:x+9]=RULE
  f[42:45,8:11+min(g.wear,7)*6]=WEAR;f[49:52,8:11+g.delay*11]=RULE;f[54:57,8:11+g.local*11]=LOCAL;f[58:60,8:11+g.global_*11]=GLOBAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q414(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q414",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.couriers=(0,1,2);self.wear=self.local=self.global_=self.delay=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.couriers,self.wear,self.local,self.global_,self.delay=advance((self.couriers,self.wear,self.local,self.global_,self.delay),a,x)
  elif a==6:
   if (self.couriers,self.wear,self.local,self.global_,self.delay)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
