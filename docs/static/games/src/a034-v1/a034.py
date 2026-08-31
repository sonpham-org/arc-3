"""a034 Queue Garden -- schedule FIFO seed channels with different visible latencies."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CHANNEL,SEED,CLOCK,BED,QUEUE,GOAL,BAD=3,10,8,14,11,6,12,13,15
LEVELS=[{"name":"First Enqueue","seq":(1,)},{"name":"Second Channel","seq":(2,1)},{"name":"FIFO Emergence","seq":(3,1,2)},{"name":"Delay Tick","seq":(4,2,1,3)},{"name":"Shared Bed","seq":(2,3,1,4,2,1)},{"name":"Queue Garden","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 queues,active,tick,beds,next_seed,schedule=s;q=[list(x) for x in queues];b=list(beds)
 if a==1:q[active].append((next_seed,tick+(active+1)*2));next_seed=(next_seed+1)%6
 elif a==2:active=(active+1)%3
 elif a==3:
  tick+=1
  for i in range(3):
   if q[i] and q[i][0][1]<=tick:b.append((i,q[i].pop(0)[0],tick))
 elif a==4:tick+=2
 elif a==5:schedule=(tuple(map(tuple,q)),active,tick,tuple(b[-5:]),next_seed)
 return tuple(map(tuple,q)),active,tick,tuple(b),next_seed,schedule
for x in LEVELS:
 s=(((),(),()),0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  f[1:4,8:28]=SEED;f[1:4,32:52]=QUEUE
  for i,q in enumerate(g.queues):y=8+i*11;f[y:y+8,7:57]=CHANNEL
  for i,q in enumerate(g.queues):
   y=9+i*11
   for j,_ in enumerate(q[-5:]):f[y:y+6,9+j*9:16+j*9]=QUEUE if i==g.active else SEED
  for i,(_,s,_) in enumerate(g.beds[-4:]):f[44:50,8+i*12:17+i*12]=BED;f[51:54,8+i*12:10+i*12+s]=SEED
  f[56:60,8:8+(g.tick%6)*8+7]=CLOCK
  if g.schedule:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A034(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a034",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.queues=((),(),());self.active=self.tick=self.next_seed=0;self.beds=();self.schedule=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.queues,self.active,self.tick,self.beds,self.next_seed,self.schedule=advance((self.queues,self.active,self.tick,self.beds,self.next_seed,self.schedule),a)
  elif a==6:
   if (self.queues,self.active,self.tick,self.beds,self.next_seed,self.schedule)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
