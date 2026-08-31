"""a055 Perishable Queue -- track both order and age with a single siding."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MARKET,RAIL,FRESH,AGING,OLD,SIDING,SERVE,DISCARD,BAD=15,8,9,10,12,14,11,13,6,4
LEVELS=[
 {"name":"Fresh Arrival","seq":(1,)},{"name":"Age Once","seq":(1,2)},
 {"name":"Serve Front","seq":(1,2,3)},{"name":"Use Siding","seq":(1,1,4,2,3)},
 {"name":"Protect Later","seq":(1,2,1,4,2,3,4)},{"name":"Perishable Queue","seq":(1,1,2,4,1,2,3,4,2,3)},
]
def advance(s,a):
 queue,siding,color,served,discarded,history,snapshot=s;q=list(queue);side=list(siding)
 if a==1:q.append((color,0));q=q[-6:];color=(color+1)%3;history=(history+(1,))[-8:]
 elif a==2:q=[(c,min(4,age+1)) for c,age in q];side=[(c,min(4,age+1)) for c,age in side];history=(history+(2,))[-8:]
 elif a==3:
  if q:
   c,age=q.pop(0)
   if age<4:served=(served+(c,))[-6:]
   else:discarded=(discarded+1)%6
  history=(history+(3,))[-8:]
 elif a==4:
  if not side and q:side.append(q.pop(0))
  elif side:q.append(side.pop(0))
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(q),tuple(side),color,served,discarded,history)
 return tuple(q),tuple(side),color,served,discarded,history,snapshot
for x in LEVELS:
 s=((),(),0,(),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MARKET;f[22:35,6:57]=RAIL;f[40:51,17:43]=SIDING
  ages=(FRESH,AGING,OLD,BAD)
  for i,(c,age) in enumerate(g.queue):x=8+i*8;f[24:33,x:x+7]=ages[age];f[26:31,x+2:x+5]=(FRESH,AGING,OLD)[c]
  for i,(c,age) in enumerate(g.siding):x=20+i*9;f[41:49,x:x+7]=ages[age]
  f[14:20,8:20]=(FRESH,AGING,OLD)[g.color]
  for i,v in enumerate(g.served):f[53:57,8+i*7:14+i*7]=SERVE
  for i in range(g.discarded):f[8:11,34+i*4:37+i*4]=DISCARD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A055(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a055",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.queue,self.siding,self.color,self.served,self.discarded,self.history,self.snapshot=((),(),0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.queue,self.siding,self.color,self.served,self.discarded,self.history,self.snapshot=advance((self.queue,self.siding,self.color,self.served,self.discarded,self.history,self.snapshot),a)
  elif a==6:
   if (self.queue,self.siding,self.color,self.served,self.discarded,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
