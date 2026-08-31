"""q725 Waystation Gradient -- route conserved caravan mass through repetition-sensitive dunes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,BIN0,BIN1,BIN2,DUNE,PHASE,TARGET,GOAL,BAD=7,4,11,10,14,12,9,6,13,15
LEVELS=[
 {"name":"One Transfer","initial":(4,0,0),"cap":6,"seq":(1,)},
 {"name":"Middle Route","initial":(3,2,0),"cap":6,"seq":(2,)},
 {"name":"Conserved Caravan","initial":(4,1,0),"cap":6,"seq":(1,2)},
 {"name":"Rotated Dunes","initial":(5,1,0),"cap":6,"seq":(1,3,2)},
 {"name":"Repeated Toll","initial":(6,1,1),"cap":7,"seq":(1,1,1,2,3,4)},
 {"name":"Waystation Gradient","initial":(6,2,1),"cap":7,"seq":(1,2,1,3,2,2,4,1)}]
def advance(s,a,x):
 bins,phase,recent,tolls,committed=s;b=list(bins)
 if a in (1,2):
  kind=a-1;punished=len(recent)==2 and recent[0]==recent[1]==kind;nmax=1 if punished else 2;i=kind;n=min(nmax,b[i],x["cap"]-b[i+1]);b[i]-=n;b[i+1]+=n;recent=(recent+(kind,))[-2:];tolls+=int(punished)
 elif a==3:b=[b[2],b[0],b[1]];phase=(phase+1)%3
 elif a==4:
  n=min(1,b[2],x["cap"]-b[0]);b[2]-=n;b[0]+=n
 elif a==5:committed=(tuple(b),phase,tolls,tuple(recent))
 assert sum(b)==sum(x["initial"])
 return tuple(b),phase,recent,tolls,committed
for x in LEVELS:
 s=(x["initial"],0,(),0,None)
 for a in x["seq"]:s=advance(s,a,x)
 x["goal"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND;cols=(BIN0,BIN1,BIN2)
  for i,v in enumerate(g.bins):x=8+i*18;f[9:39,x:x+14]=DUNE;f[38-v*4:38,x+2:x+12]=cols[i]
  for i,v in enumerate(g.cfg["goal"]):x=8+i*18;f[43:47,x:x+min(v,7)*2]=TARGET
  f[51:55,8:8+g.phase*15+10]=PHASE
  for i,v in enumerate(g.recent):f[56:60,8+i*12:17+i*12]=cols[v]
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q725(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q725",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.phase=self.tolls=0;self.recent=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.phase,self.recent,self.tolls,self.committed=advance((self.bins,self.phase,self.recent,self.tolls,self.committed),a,self.cfg)
  elif a==6:
   if (self.bins,self.phase,self.recent,self.tolls,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
