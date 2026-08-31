"""q793 Impeller Rhythm -- interrupt counter-rotating macros before repeated samples become costly."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,RING,BLADE,MACRO,TICK,PERIOD,WAKE,COST,WINDOW,BAD=10,1,6,14,11,12,9,7,5,13,15
LEVELS=[
 {"name":"Single Tick","seq":(2,)},{"name":"First Macro","seq":(1,)},
 {"name":"Reversed Routine","seq":(3,1)},{"name":"Sampled Window","seq":(1,2,4)},
 {"name":"Counter Rhythm","seq":(1,3,1,2,4)},{"name":"Impeller Rhythm","seq":(1,2,3,1,4,3,2,1)}]
def advance(s,a,x,check=True):
 phase,period,direction,memory,cost,interrupted=s
 if a==1:phase=(phase+direction*period)%12
 elif a==2:phase=(phase+direction)%12
 elif a==3:direction*=-1;period=2+(period-1)%3
 elif a==4:cost+=2 if memory and memory[-1]==phase else 1;memory=memory+(phase,)
 elif a==5:
  if check and (phase!=x["window"] or not memory):return None
  interrupted=(phase,period,direction,len(memory),cost)
 return phase,period,direction,memory,cost,interrupted
for x in LEVELS:
 s=(0,2,1,(),0,None)
 for a in x["seq"]:s=advance(s,a,x,False)
 if not s[3]:s=advance(s,4,x,False);x["seq"]=x["seq"]+(4,)
 x["window"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,2,1,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(12):x=7+(i%6)*9;y=10+(i//6)*12;f[y:y+5,x:x+5]=BLADE if i==g.phase else RING
  wx=7+(g.cfg["window"]%6)*9;wy=10+(g.cfg["window"]//6)*12;f[wy+6:wy+9,wx:wx+5]=WINDOW
  f[38:43,8:8+g.period*10]=PERIOD;f[47:51,8:28]=WAKE if g.direction>0 else MACRO
  for i,v in enumerate(g.memory[-4:]):f[53:57,8+i*11:16+i*11]=TICK if v%2 else MACRO
  f[57:60,8:8+min(g.cost,9)*5]=COST
  if g.interrupted:f[55:59,43:56]=WINDOW
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q793(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q793",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=0;self.period=2;self.direction=1;self.memory=();self.cost=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.phase,self.period,self.direction,self.memory,self.cost,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.phase,self.period,self.direction,self.memory,self.cost,self.interrupted=s
  elif a==6:
   if (self.phase,self.period,self.direction,self.memory,self.cost,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
