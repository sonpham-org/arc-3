"""q200 Clock of Clocks -- compose local cycles into higher-level transitions."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLOCKWORK,CLOCK,TICK,EVENT,MACRO,TRIGGER,GOAL,BAD=8,10,9,14,12,5,11,6,15
LEVELS=[{"name":"One Local Cycle","periods":(2,2,2),"macro":1,"plan":(1,1,4,5)},{"name":"Three-Tick Clock","periods":(2,3,2),"macro":1,"plan":(2,2,2,4,5)},{"name":"Clock Conjunction","periods":(2,3,4),"macro":1,"plan":(1,1,2,2,2,3,3,3,3,4,5)},{"name":"Two Macro States","periods":(2,3,4),"macro":2,"plan":(1,1,2,2,2,4,3,3,3,3,4,5)},{"name":"Nested Return","periods":(3,2,3),"macro":2,"plan":(1,1,1,2,2,4,3,3,3,4,5)},{"name":"Clock of Clocks","periods":(3,4,5),"macro":3,"plan":(1,1,1,4,2,2,2,2,4,3,3,3,3,3,4,5)}]
def advance(s,a,x):
 clocks,events,macro,trace,committed=s;clocks=list(clocks);trace=list(trace)
 if a in (1,2,3):i=a-1;clocks[i]=(clocks[i]+1)%x["periods"][i];events+=1 if clocks[i]==0 else 0;trace.append((a,tuple(clocks)))
 elif a==4:
  if any(clocks):return None
  macro=(macro+1)%4;trace.append((4,macro,events))
 elif a==5:
  if macro!=x["macro"]:return None
  committed=(tuple(clocks),events,macro,tuple(trace))
 return tuple(clocks),events,macro,tuple(trace),committed
def target(x):
 s=((0,0,0),0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CLOCKWORK
  for i,v in enumerate(g.clocks):x=8+i*18;f[8:33,x:x+14]=CLOCK;f[13+v*5:19+v*5,x+4:x+10]=TICK-i
  f[39:42,8:11+(g.events%5)*9]=EVENT;f[46:49,8:11+g.macro*12]=MACRO;f[53:56,8:24]=TRIGGER;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q200(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q200",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.clocks=(0,0,0);self.events=self.macro=0;self.trace=();self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.clocks,self.events,self.macro,self.trace,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.clocks,self.events,self.macro,self.trace,self.committed=s
  elif a==6:
   if (self.clocks,self.events,self.macro,self.trace,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
