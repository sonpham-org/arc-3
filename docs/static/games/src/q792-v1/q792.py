"""q792 Semaphore Rhythm -- interrupt a signal macro after two miniature phase tests."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,FLAG,BEAM,FAST,SLOW,TEST,GOAL,BAD=9,1,14,10,6,12,11,13,15
LEVELS=[{"name":"Flag Tick","seq":(1,)},{"name":"Relay Cycle","seq":(1,1,2)},{"name":"Test Pulse","seq":(3,1,2,1)},{"name":"Phase Window","seq":(1,2,1,3,2)},{"name":"Macro Test","seq":(2,1,3,1,2,1,1)},{"name":"Semaphore Rhythm","seq":(1,2,3,1,1,2,1,3,2,1,1)}]
def advance(s,a):
 fast,slow,beam,tests,ticks,interrupted=s
 if a==1:
  fast=(fast+1)%4;ticks+=1;beam=(beam+1+len(tests))%6
  if fast==0:slow=(slow+1)%5
 elif a==2:fast=(fast+2)%4;slow=(slow+1)%5;beam=(beam+2)%6;ticks+=2
 elif a==3:tests=tests+((fast,slow,beam),);beam=(beam+len(tests))%6
 elif a==4:fast=slow=beam=0;ticks+=1
 elif a==5:interrupted=(fast,slow,beam,tests[-3:],ticks)
 return fast,slow,beam,tests,ticks,interrupted
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*14;f[y:y+10,x:x+7]=BEAM;f[y+3:y+7,x+2:x+5]=FLAG if i==g.beam else TEST
  for i,t in enumerate(g.tests[-4:]):x=8+i*12;f[38:43,x:x+9]=TEST;f[44:46,x:x+2+t[0]*2]=FLAG
  f[50:54,8:8+g.fast*12+8]=FAST;f[56:60,8:8+g.slow*9+7]=SLOW
  if g.interrupted:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q792(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q792",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fast=self.slow=self.beam=self.ticks=0;self.tests=();self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fast,self.slow,self.beam,self.tests,self.ticks,self.interrupted=advance((self.fast,self.slow,self.beam,self.tests,self.ticks,self.interrupted),a)
  elif a==6:
   if (self.fast,self.slow,self.beam,self.tests,self.ticks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
