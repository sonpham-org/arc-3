"""q633 Murmuration Sandbox -- reset flock trials while parity evidence persists."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,AVIARY,FLOCK,WIND,EVIDENCE,RESET,GOAL,BAD=4,9,11,14,10,6,12,13,15
LEVELS=[
 {"name":"First Trial","seq":(1,3)},{"name":"Wind Swap","seq":(2,3,4)},
 {"name":"Persistent Parity","seq":(1,3,4,2,3)},{"name":"Flock Contrast","seq":(2,1,3,4,1,3)},
 {"name":"Two Wakes","seq":(1,2,3,4,2,2,3)},
 {"name":"Murmuration Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 flock,wind,parity,evidence,trials,commit=s;v=list(flock)
 if a==1:v[0],v[1]=v[1],v[0];wind=(wind+1)%4;parity^=1
 elif a==2:v=v[1:]+v[:1];wind=(wind+2)%4;parity^=(sum(v)%2)
 elif a==3:evidence=evidence+((tuple(v),wind,parity),);trials+=1
 elif a==4:v[:]=[0,1,2];wind=parity=0
 elif a==5:commit=(tuple(v),wind,parity,evidence[-3:],trials)
 return tuple(v),wind,parity,evidence,trials,commit
for x in LEVELS:
 s=((0,1,2),0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=AVIARY;f[8:31,35:57]=RESET
  for i,v in enumerate(g.flock):x=9+i*7;f[24-v*4:29,x:x+6]=FLOCK
  for i,e in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+e[2]*3]=WIND
  f[50:54,8:8+g.wind*11+7]=WIND;f[55:59,8:8+g.parity*25+12]=EVIDENCE
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q633(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q633",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.flock=(0,1,2);self.wind=self.parity=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.flock,self.wind,self.parity,self.evidence,self.trials,self.commit=advance((self.flock,self.wind,self.parity,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.flock,self.wind,self.parity,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
