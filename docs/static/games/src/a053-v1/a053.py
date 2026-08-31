"""a053 Service Rhythm -- route persistent queues across alternating rates."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,DEPOT,QUEUE,STATION_A,STATION_B,PHASE,ITEM,SERVICE,REROUTE,BAD=13,8,9,12,14,10,11,6,4,15
LEVELS=[
 {"name":"Route Arrival","seq":(1,)},{"name":"Change Route","seq":(2,1)},
 {"name":"Fast Phase","seq":(1,3)},{"name":"Anticipate Shift","seq":(1,2,4,1,3)},
 {"name":"Retained Queue","seq":(1,1,3,4,2,1,3)},{"name":"Service Rhythm","seq":(1,2,1,3,4,1,2,3,4,3)},
]
def advance(s,a):
 queues,route,phase,served,clock,history,snapshot=s;q=list(queues);sv=list(served)
 if a==1:q[route]=min(7,q[route]+1);clock=(clock+1)%8;history=(history+(1,))[-8:]
 elif a==2:route^=1;history=(history+(2,))[-8:]
 elif a==3:
  rates=(2,1) if phase==0 else (1,2)
  for i in range(2):n=min(q[i],rates[i]);q[i]-=n;sv[i]+=n
  clock=(clock+1)%8;history=(history+(3,))[-8:]
 elif a==4:phase^=1;clock=0;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(q),route,phase,tuple(sv),clock,history)
 return tuple(q),route,phase,tuple(sv),clock,history,snapshot
for x in LEVELS:
 s=((0,0),0,0,(0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DEPOT
  for i,col in enumerate((STATION_A,STATION_B)):
   y=13+i*27;f[y:y+15,42:57]=col;f[y+4:y+10,8:42]=QUEUE
   for j in range(g.queues[i]):f[y+3:y+11,9+j*4:12+j*4]=ITEM
   for j in range(min(6,g.served[i])):f[y+17:y+21,11+j*5:15+j*5]=SERVICE
  f[7:11,9:27]=PHASE if g.phase==0 else REROUTE;f[30:36,9:17]=STATION_A if g.route==0 else STATION_B
  for i in range(g.clock):f[55:58,9+i*5:13+i*5]=PHASE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A053(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a053",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.queues,self.route,self.phase,self.served,self.clock,self.history,self.snapshot=((0,0),0,0,(0,0),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.queues,self.route,self.phase,self.served,self.clock,self.history,self.snapshot=advance((self.queues,self.route,self.phase,self.served,self.clock,self.history,self.snapshot),a)
  elif a==6:
   if (self.queues,self.route,self.phase,self.served,self.clock,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
