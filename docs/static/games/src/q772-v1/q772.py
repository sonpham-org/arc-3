"""q772 Tide Rhythm -- interrupt a reversing-current macro only after safe evidence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,SHELL,CURRENT,FAST,SLOW,GATE,GOAL,BAD=9,1,14,10,6,12,11,13,15
LEVELS=[
 {"name":"Current Tick","seq":(1,)},{"name":"Tidal Cycle","seq":(1,1,2)},
 {"name":"Evidence Pulse","seq":(3,1,2,1)},{"name":"Safe Window","seq":(1,2,1,3,2)},
 {"name":"Delayed Gate","seq":(2,1,3,1,2,1,1)},
 {"name":"Tide Rhythm","seq":(1,2,3,1,1,2,1,3,2,1,1)}]
def advance(s,a):
 fast,slow,current,evidence,gate,ticks,interrupted=s
 if a==1:
  fast=(fast+1)%4;ticks+=1
  if fast==0:slow=(slow+1)%5;current^=1
 elif a==2:fast=(fast+2)%4;slow=(slow+1)%5;current^=1;ticks+=2
 elif a==3:evidence=evidence+((fast,slow,current),);gate=(gate+len(evidence)+current)%4
 elif a==4:gate=(gate+1)%4;ticks+=1
 elif a==5:interrupted=(fast,slow,current,evidence[-3:],gate,ticks)
 return fast,slow,current,evidence,gate,ticks,interrupted
for x in LEVELS:
 s=(0,0,0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN
  for i in range(12):x=7+(i%6)*9;y=8+(i//6)*15;f[y:y+11,x:x+7]=CURRENT;f[y+3:y+8,x+2:x+5]=SHELL if i in (g.fast,g.slow+6) else GATE
  for i,e in enumerate(g.evidence[-4:]):x=8+i*12;f[39:44,x:x+9]=GATE;f[45:47,x:x+2+e[2]*4]=CURRENT
  f[49:53,8:8+g.fast*12+8]=FAST;f[55:59,8:8+g.slow*9+7]=SLOW
  if g.interrupted:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q772(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q772",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fast=self.slow=self.current=self.gate=self.ticks=0;self.evidence=();self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fast,self.slow,self.current,self.evidence,self.gate,self.ticks,self.interrupted=advance((self.fast,self.slow,self.current,self.evidence,self.gate,self.ticks,self.interrupted),a)
  elif a==6:
   if (self.fast,self.slow,self.current,self.evidence,self.gate,self.ticks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
