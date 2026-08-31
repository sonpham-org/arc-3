"""q543 Murmuration Lesson -- infer a contextual flock policy despite one parity-detectable decoy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,WIND,DEMO,CONTEXT,PARITY,GOAL,BAD=1,9,14,10,6,12,11,13,15
LEVELS=[
 {"name":"One Example","seq":(1,)},{"name":"Context Wind","seq":(4,2)},
 {"name":"Decoy Gesture","seq":(1,3,2)},{"name":"Parity Policy","seq":(1,2,4,1)},
 {"name":"Collective Wake","seq":(2,1,3,4,2,1)},
 {"name":"Murmuration Lesson","seq":(1,4,2,3,1,2,4,2,1)}]
def advance(s,a):
 context,flock,wind,trace,parity,policy=s
 if a==1:flock=(flock+1+context)%8;wind=(wind+1)%4;parity^=(flock%2);trace=trace+((context,1,flock),)
 elif a==2:flock=(flock+2+wind)%8;wind=(wind+2)%4;parity^=1;trace=trace+((context,2,flock),)
 elif a==3:trace=trace+((context,0,flock),);parity^=1
 elif a==4:context^=1;parity^=context
 elif a==5:policy=(context,flock,wind,trace[-4:],parity)
 return context,flock,wind,trace,parity,policy
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=AVIARY
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*14;f[y:y+10,x:x+7]=WIND;f[y+3:y+7,x+2:x+5]=FLOCK if i==g.flock else CONTEXT
  for i,(_,a,v) in enumerate(g.trace[-5:]):x=8+i*10;f[38:43,x:x+7]=DEMO if a else PARITY;f[44:46,x:x+2+v%5]=FLOCK
  f[50:54,8:8+g.wind*11+7]=CONTEXT;f[56:60,8:8+g.parity*25+12]=PARITY
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q543(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q543",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.flock=self.wind=self.parity=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.flock,self.wind,self.trace,self.parity,self.policy=advance((self.context,self.flock,self.wind,self.trace,self.parity,self.policy),a)
  elif a==6:
   if (self.context,self.flock,self.wind,self.trace,self.parity,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
