"""q733 Impeller Gradient -- route conserved blade mass around capacity-limited wake rings."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BIN0,BIN1,BIN2,BIN3,RING,WAKE,TARGET,GOAL,BAD=7,4,11,10,14,12,6,9,5,13,15
LEVELS=[
 {"name":"One Wake","initial":(4,0,0,0),"cap":6,"seq":(1,)},
 {"name":"Second Wake","initial":(3,2,0,0),"cap":6,"seq":(2,)},
 {"name":"Conserved Ring","initial":(4,1,0,0),"cap":6,"seq":(1,2)},
 {"name":"Counter Rotation","initial":(5,1,0,0),"cap":6,"seq":(1,3,2)},
 {"name":"Four Reservoirs","initial":(5,2,1,0),"cap":6,"seq":(1,2,3,1,4)},
 {"name":"Impeller Gradient","initial":(6,2,1,0),"cap":7,"seq":(1,1,2,3,2,4,1,3)}]
def advance(s,a,x):
 bins,direction,phase,samples,committed=s;b=list(bins)
 if a in (1,2):
  edge=a-1;i=edge if direction>0 else 3-edge;j=i+1 if direction>0 else i-1;n=min(2,b[i],x["cap"]-b[j]);b[i]-=n;b[j]+=n
 elif a==3:b=b[1:]+b[:1];direction*=-1;phase=(phase+1)%4
 elif a==4:samples+=1
 elif a==5:committed=(tuple(b),direction,phase,samples)
 assert sum(b)==sum(x["initial"])
 return tuple(b),direction,phase,samples,committed
for x in LEVELS:
 s=(x["initial"],1,0,0,None)
 for a in x["seq"]:s=advance(s,a,x)
 x["goal"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],1,0,0,None)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(BIN0,BIN1,BIN2,BIN3)
  for i,v in enumerate(g.bins):x=7+i*14;f[9:38,x:x+11]=RING;f[37-v*4:37,x+2:x+9]=cols[i]
  for i,v in enumerate(g.cfg["goal"]):x=7+i*14;f[42:46,x:x+min(v,7)]=TARGET
  f[50:54,8:8+g.phase*12+8]=WAKE if g.direction>0 else BIN3
  if g.samples:f[56:60,8:8+min(g.samples,6)*7]=TARGET
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q733(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q733",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.direction=1;self.phase=self.samples=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.direction,self.phase,self.samples,self.committed=advance((self.bins,self.direction,self.phase,self.samples,self.committed),a,self.cfg)
  elif a==6:
   if (self.bins,self.direction,self.phase,self.samples,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
