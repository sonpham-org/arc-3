"""a050 Spillback City -- preserve escape capacity across a signal grid."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CITY,ROAD,CAR_E,CAR_N,LIGHT,EMPTY,BLOCK,FLOW,BAD=10,8,9,12,14,11,13,4,6,15
LEVELS=[
 {"name":"East Green","seq":(1,)},{"name":"Reserve Exit","seq":(4,1)},
 {"name":"North Green","seq":(3,2)},{"name":"Protect Junction","seq":(4,1,3,2,4)},
 {"name":"Spillback Chain","seq":(1,4,3,2,2,4,1)},{"name":"Spillback City","seq":(4,1,3,2,4,2,3,1,4)},
]
def advance(s,a):
 queues,signal,escape,blocked,history,snapshot=s;q=list(queues)
 if a==1:
  lane=signal%2
  if escape[lane] and q[lane]:q[lane]-=1;q[(lane+2)%4]=min(4,q[(lane+2)%4]+1)
  else:blocked=(blocked+1)%6
  history=(history+(1,))[-8:]
 elif a==2:
  lane=1+(signal%2)
  if escape[lane] and q[lane]:q[lane]-=1;q[(lane+1)%4]=min(4,q[(lane+1)%4]+1)
  else:blocked=(blocked+2)%6
  history=(history+(2,))[-8:]
 elif a==3:signal=(signal+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  e=list(escape);e[signal%4]^=1;e[(signal+2)%4]=1;escape=tuple(e);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(q),signal,escape,blocked,history)
 return tuple(q),signal,escape,blocked,history,snapshot
for x in LEVELS:
 s=((2,3,1,2),0,(1,0,1,0),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CITY;f[25:39,5:59]=ROAD;f[5:59,25:39]=ROAD
  lanes=((7,28,1,0),(42,28,-1,1),(28,7,0,2),(28,42,0,3))
  for x,y,dx,i in lanes:
   for j in range(g.queues[i]):
    xx=x+j*6*dx;yy=y+j*6*(1 if dx==0 else 0);f[yy:yy+6,xx:xx+8]=CAR_E if i%2==0 else CAR_N
  for i,(x,y) in enumerate(((19,20),(40,20),(40,41),(19,41))):f[y:y+6,x:x+6]=EMPTY if g.escape[i] else BLOCK
  sx,sy=((20,30),(38,20),(38,38),(20,38))[g.signal];f[sy:sy+6,sx:sx+6]=LIGHT
  for i in range(g.blocked):f[8:12,44+i*2:46+i*2]=BAD
  for i,v in enumerate(g.history[-8:]):f[54:57,10+i*5:14+i*5]=FLOW if v in (1,2) else LIGHT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A050(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a050",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.queues,self.signal,self.escape,self.blocked,self.history,self.snapshot=((2,3,1,2),0,(1,0,1,0),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.queues,self.signal,self.escape,self.blocked,self.history,self.snapshot=advance((self.queues,self.signal,self.escape,self.blocked,self.history,self.snapshot),a)
  elif a==6:
   if (self.queues,self.signal,self.escape,self.blocked,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
