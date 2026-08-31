"""q724 Moraine Gradient -- turn conserved local flow into ordered outer tokens."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,BIN0,BIN1,BIN2,CREVASSE,PHASE,OUTER,GOAL,BAD=7,4,11,10,14,12,9,6,13,15
LEVELS=[
 {"name":"One Flow","initial":(4,0,0),"cap":6,"seq":(1,)},
 {"name":"Second Flow","initial":(3,2,0),"cap":6,"seq":(2,)},
 {"name":"Conserved Moraine","initial":(4,1,0),"cap":6,"seq":(1,2)},
 {"name":"Rotated Crevasse","initial":(5,1,0),"cap":6,"seq":(1,3,2)},
 {"name":"Outer Gradient","initial":(5,2,1),"cap":6,"seq":(1,2,3,1,2)},
 {"name":"Moraine Gradient","initial":(6,2,1),"cap":7,"seq":(1,1,2,3,2,1,3)}]
def advance(s,a,x):
 bins,phase,outer,order,committed=s;b=list(bins);outer=list(outer)
 if a in (1,2):i=a-1;n=min(2,b[i],x["cap"]-b[i+1]);b[i]-=n;b[i+1]+=n
 elif a==3:b=[b[2],b[0],b[1]];phase=(phase+1)%3
 elif a==4:outer[phase]=(sum((i+1)*v for i,v in enumerate(b))%4);order=order+(phase,)
 elif a==5:committed=(tuple(b),phase,tuple(outer),order)
 assert sum(b)==sum(x["initial"])
 return tuple(b),phase,tuple(outer),order,committed
for x in LEVELS:
 s=(x["initial"],0,(0,0,0),(),None)
 for a in x["seq"]:s=advance(s,a,x)
 x["goal"]=s[0];x["plan"]=x["seq"]+(4,5)
def target(x):
 s=(x["initial"],0,(0,0,0),(),None)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE;cols=(BIN0,BIN1,BIN2)
  for i,v in enumerate(g.bins):x=8+i*18;f[9:38,x:x+14]=CREVASSE;f[37-v*4:37,x+2:x+12]=cols[i]
  for i,v in enumerate(g.outer):f[43:47,8+i*16:8+i*16+v*3+4]=OUTER
  f[51:55,8:8+g.phase*15+10]=PHASE
  for i,v in enumerate(g.order[-4:]):f[56:60,8+i*10:15+i*10]=cols[v]
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q724(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q724",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.phase=0;self.outer=(0,0,0);self.order=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.phase,self.outer,self.order,self.committed=advance((self.bins,self.phase,self.outer,self.order,self.committed),a,self.cfg)
  elif a==6:
   if (self.bins,self.phase,self.outer,self.order,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
