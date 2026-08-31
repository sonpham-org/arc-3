"""q737 Spectrum Gradient -- move conserved spectral mass through phase-rotated channels."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BAND0,BAND1,BAND2,CHANNEL,PHASE,TARGET,GOAL,BAD=7,4,11,10,14,6,9,12,13,15
LEVELS=[
 {"name":"One Channel","initial":(4,0,0),"cap":6,"seq":(1,)},
 {"name":"Second Channel","initial":(3,2,0),"cap":6,"seq":(2,)},
 {"name":"Conserved Spectrum","initial":(4,1,0),"cap":6,"seq":(1,2)},
 {"name":"Rotated Bands","initial":(5,1,0),"cap":6,"seq":(1,3,2)},
 {"name":"Capacity Gradient","initial":(5,2,1),"cap":6,"seq":(1,2,3,4,1)},
 {"name":"Spectrum Gradient","initial":(6,2,1),"cap":7,"seq":(1,1,2,3,2,4,1,3)}]
def advance(s,a,x):
 bins,phase,pulses,committed=s;b=list(bins)
 if a==1:
  n=min(2,b[0],x["cap"]-b[1]);b[0]-=n;b[1]+=n
 elif a==2:
  n=min(2,b[1],x["cap"]-b[2]);b[1]-=n;b[2]+=n
 elif a==3:b=[b[2],b[0],b[1]];phase=(phase+1)%3
 elif a==4:
  n=min(1,b[2],x["cap"]-b[0]);b[2]-=n;b[0]+=n;pulses+=1
 elif a==5:committed=(tuple(b),phase,pulses)
 assert sum(b)==sum(x["initial"])
 return tuple(b),phase,pulses,committed
for x in LEVELS:
 s=(x["initial"],0,0,None)
 for a in x["seq"]:s=advance(s,a,x)
 x["goal"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],0,0,None)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(BAND0,BAND1,BAND2)
  for i,v in enumerate(g.bins):
   x=8+i*18;f[9:39,x:x+14]=CHANNEL;f[38-v*4:38,x+2:x+12]=cols[i]
  for i,v in enumerate(g.cfg["goal"]):x=8+i*18;f[43:47,x:x+min(v,7)*2]=TARGET
  f[51:55,8:8+g.phase*15+10]=PHASE
  if g.pulses:f[56:60,8:8+min(g.pulses,5)*9]=BAND2
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q737(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q737",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.phase=self.pulses=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.phase,self.pulses,self.committed=advance((self.bins,self.phase,self.pulses,self.committed),a,self.cfg)
  elif a==6:
   if (self.bins,self.phase,self.pulses,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
