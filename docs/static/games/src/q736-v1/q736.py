"""q736 Crossing Gradient -- coordinate disjoint transfer edges through marked handoffs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,BIN0,BIN1,BIN2,DOCK,MARK0,MARK1,TARGET,GOAL,BAD=7,4,11,10,14,12,6,9,5,13,15
LEVELS=[
 {"name":"First Edge","initial":(4,0,0),"cap":6,"seq":(1,)},
 {"name":"Second Controller","initial":(3,2,0),"cap":6,"seq":(1,4,3,2)},
 {"name":"Marked Flow","initial":(4,1,0),"cap":6,"seq":(1,4,3,2,4)},
 {"name":"Capacity Ferry","initial":(5,1,0),"cap":6,"seq":(1,1,4,3,2)},
 {"name":"Alternating Gradient","initial":(5,2,1),"cap":6,"seq":(1,4,3,2,4,3,1,4)},
 {"name":"Crossing Gradient","initial":(6,2,1),"cap":7,"seq":(1,1,4,3,2,4,3,1,4,3,2)}]
def advance(s,a,x):
 bins,controller,marks,phase,committed=s;b=list(bins)
 if a in (1,2):
  edge=(a-1+controller)%2;n=min(2,b[edge],x["cap"]-b[edge+1]);b[edge]-=n;b[edge+1]+=n;phase=(phase+edge+1)%3
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,tuple(b),phase),)
 elif a==5:committed=(tuple(b),controller,marks[-2:],phase)
 assert sum(b)==sum(x["initial"])
 return tuple(b),controller,marks,phase,committed
for x in LEVELS:
 s=(x["initial"],0,(),0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;cols=(BIN0,BIN1,BIN2)
  for i,v in enumerate(g.bins):x=8+i*18;f[9:38,x:x+14]=DOCK;f[37-v*4:37,x+2:x+12]=cols[i]
  for i,v in enumerate(g.cfg["goal"]):f[43:47,8+i*18:8+i*18+min(v,7)*2]=TARGET
  for i,m in enumerate(g.marks[-4:]):f[51:55,8+i*11:16+i*11]=MARK0 if m[0]==0 else MARK1
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q736(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q736",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.controller=0;self.marks=();self.phase=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.controller,self.marks,self.phase,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.controller,self.marks,self.phase,self.committed=s
  elif a==6:
   if (self.bins,self.controller,self.marks,self.phase,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
