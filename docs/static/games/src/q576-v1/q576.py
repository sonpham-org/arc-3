"""q576 Backstage Counter -- shape a rival through signed pressure and direction."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,TACTIC0,TACTIC1,TACTIC2,POSITIVE,NEGATIVE,EXPLOIT,BAD=2,13,10,14,6,11,9,12,15
LEVELS=[
 {"name":"Paired Pressure","seq":(1,1)},{"name":"Split Pressure","seq":(1,2)},
 {"name":"Reverse Rival","seq":(2,1,3)},{"name":"Threshold Counter","seq":(1,2,1,2)},
 {"name":"Decoy Cue","seq":(2,2,1,5,2)},{"name":"Backstage Counter","seq":(1,2,2,1,3,5,2)}]
def shape(s,a):
 value,direction,hist,rival,exploited=s;hist=list(hist)
 if a in (1,2):value+=direction*(2 if a==1 else -1);hist=(hist+[a])[-3:];rival=(abs(value)//2+int(direction<0)+sum(hist))%3
 elif a==3:direction*=-1;rival=(abs(value)//2+int(direction<0)+sum(hist))%3
 elif a==5:value+=direction;rival=(abs(value)//2+int(direction<0)+sum(hist))%3
 return value,direction,tuple(hist),rival,exploited
for x in LEVELS:
 s=(0,1,(),0,None)
 for a in x["seq"]:s=shape(s,a)
 x["goal"]=s[3];x["plan"]=x["seq"]+(4,)
def advance(s,a,x):
 if a==4:
  if s[3]!=x["goal"]:return None
  return s[0],s[1],s[2],s[3],(s[3],s[0],s[1])
 return shape(s,a)
def target(x):
 s=(0,1,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i,c in enumerate((TACTIC0,TACTIC1,TACTIC2)):f[8:29,8+i*17:22+i*17]=c
  width=min(abs(g.value),12)*3;f[35:40,8:8+width]=POSITIVE if g.value>=0 else NEGATIVE;f[44:48,8:28]=POSITIVE if g.direction>0 else NEGATIVE
  f[50:54,8+g.rival*17:22+g.rival*17]=EXPLOIT
  if g.exploited:f[54:59,39:56]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q576(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q576",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.value=0;self.direction=1;self.hist=();self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.value,self.direction,self.hist,self.rival,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.value,self.direction,self.hist,self.rival,self.exploited=s
  elif a==6:
   if (self.value,self.direction,self.hist,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
