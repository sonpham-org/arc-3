"""q559 Monsoon Lesson -- infer a weather policy from contextual demonstrations at phase pairs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,RAIN,STORM,DEMO,FAST,SLOW,GOAL,BAD=1,9,14,10,6,11,12,13,15
LEVELS=[{"name":"One Example","seq":(1,)},{"name":"Context Storm","seq":(4,2)},{"name":"Null Drop","seq":(1,3,2)},{"name":"Phase Policy","seq":(1,2,4,1)},{"name":"Unequal Clocks","seq":(2,1,3,4,2,1)},{"name":"Monsoon Lesson","seq":(1,4,2,3,1,2,4,2,1)}]
def advance(s,a):
 context,rain,fast,slow,trace,policy=s
 if a==1:rain=(rain+1+context)%8;fast=(fast+1)%4;slow=(slow+int(fast==0))%5;trace=trace+((context,1,rain),)
 elif a==2:rain=(rain+2+slow)%8;fast=(fast+2)%4;slow=(slow+1)%5;trace=trace+((context,2,rain),)
 elif a==3:trace=trace+((context,0,rain),)
 elif a==4:context^=1;slow=(slow+context)%5
 elif a==5:policy=(context,rain,fast,slow,trace[-4:])
 return context,rain,fast,slow,trace,policy
for x in LEVELS:
 s=(0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*14;f[y:y+10,x:x+7]=STORM;f[y+3:y+7,x+2:x+5]=RAIN if i==g.rain else FAST
  for i,(_,a,v) in enumerate(g.trace[-5:]):x=8+i*10;f[38:43,x:x+7]=DEMO if a else SLOW;f[44:46,x:x+2+v%5]=RAIN
  f[50:54,8:8+g.fast*12+8]=FAST;f[56:60,8:8+g.slow*9+7]=SLOW
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q559(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q559",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.rain=self.fast=self.slow=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.rain,self.fast,self.slow,self.trace,self.policy=advance((self.context,self.rain,self.fast,self.slow,self.trace,self.policy),a)
  elif a==6:
   if (self.context,self.rain,self.fast,self.slow,self.trace,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
