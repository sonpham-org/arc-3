"""a001 Dead Bulb Atlas -- localize one hidden circuit fault with discriminating pulses."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WALL,LAMP,WIRE,PULSE,JUNCTION,CLUE,GOAL,BAD=0,10,14,8,6,11,12,13,15
LEVELS=[{"name":"One Junction","seq":(1,)},{"name":"Sibling Branch","seq":(2,1)},{"name":"Three Pulses","seq":(3,1,2)},{"name":"Rerouted Atlas","seq":(4,2,1,3)},{"name":"Discriminating Set","seq":(2,3,1,4,2,1)},{"name":"Dead Bulb Atlas","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 fault,branch,pulses,evidence,replaced=s
 if a in (1,2,3):
  j=(a-1+branch)%3;pattern=tuple(int(((i//2)+j)%3!=fault) for i in range(6));pulses=pulses+(j,);evidence=evidence+((j,pattern),)
 elif a==4:branch=(branch+1)%3
 elif a==5:replaced=(fault,branch,pulses[-4:],evidence[-4:])
 return fault,branch,pulses,evidence,replaced
for x in LEVELS:
 s=(2,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WALL
  for j in range(3):x=9+j*17;f[9:14,x:x+12]=JUNCTION;f[14:18,x+5:x+7]=WIRE
  pattern=g.evidence[-1][1] if g.evidence else (1,1,1,1,1,1)
  for i,on in enumerate(pattern):x=8+(i%3)*18;y=21+(i//3)*11;f[y:y+8,x:x+12]=LAMP if on else CLUE
  for i,(j,_) in enumerate(g.evidence[-4:]):x=8+i*12;f[45:50,x:x+9]=PULSE;f[51:54,x:x+2+j*2]=JUNCTION
  if g.replaced:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A001(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a001",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fault=2;self.branch=0;self.pulses=self.evidence=();self.replaced=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fault,self.branch,self.pulses,self.evidence,self.replaced=advance((self.fault,self.branch,self.pulses,self.evidence,self.replaced),a)
  elif a==6:
   if (self.fault,self.branch,self.pulses,self.evidence,self.replaced)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
