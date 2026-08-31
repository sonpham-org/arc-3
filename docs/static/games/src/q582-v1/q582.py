"""q582 Semaphore Counter -- shape a rival through two visible miniature signal systems."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,FLAG,BEAM,MINI,RIVAL,HISTORY,GOAL,BAD=2,10,14,9,6,12,11,13,15
LEVELS=[
 {"name":"First Tactic","seq":(1,)},{"name":"Second Testbed","seq":(2,1)},
 {"name":"Beam Treatment","seq":(3,1,2)},{"name":"Shape Then Signal","seq":(1,4,2,3)},
 {"name":"Counter Policy","seq":(2,3,1,4,2,1)},
 {"name":"Semaphore Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 recent,rival,tests,beam,flag,exploit=s
 if a in (1,2):recent=(recent+(a,))[-2:];tests=list(tests);tests[a-1]=(tests[a-1]+a+rival)%4;tests=tuple(tests);rival=(sum(recent)+sum(tests)+beam)%3
 elif a==3:beam=(beam+1+rival)%5;flag=(flag+beam)%6
 elif a==4:flag=(flag+2+rival)%6;rival=(rival+flag)%3
 elif a==5:exploit=(recent,rival,tests,beam,flag)
 return recent,rival,tests,beam,flag,exploit
for x in LEVELS:
 s=((),0,(0,0),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;f[8:29,7:29]=MINI;f[8:29,35:57]=BEAM
  for i,v in enumerate(g.tests):x=10+i*28;f[13:24,x:x+13]=FLAG;f[17:21,x+3:x+5+v*2]=HISTORY
  for i,a in enumerate(g.recent):f[35:41,9+i*20:23+i*20]=HISTORY;f[37:39,12+i*20:12+i*20+a*4]=FLAG
  f[46:51,8:8+g.rival*16+8]=RIVAL;f[54:58,8:8+g.flag*8+5]=FLAG
  if g.exploit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q582(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q582",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.rival=0;self.tests=(0,0);self.beam=self.flag=0;self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.rival,self.tests,self.beam,self.flag,self.exploit=advance((self.recent,self.rival,self.tests,self.beam,self.flag,self.exploit),a)
  elif a==6:
   if (self.recent,self.rival,self.tests,self.beam,self.flag,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
