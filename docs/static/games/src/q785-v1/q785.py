"""q785 Waystation Rhythm -- interrupt caravan macros after repetition changes the rival rhythm."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,TRACK,WALKER,MACRO0,MACRO1,PERIOD,HISTORY,WINDOW,BAD=10,1,6,14,11,12,9,7,13,15
LEVELS=[
 {"name":"Single Step","seq":(2,)},{"name":"First Caravan","seq":(1,)},
 {"name":"Changed Pace","seq":(3,1)},{"name":"Remembered Rest","seq":(1,4,2)},
 {"name":"Repeat Counter","seq":(1,1,3,2,4,1)},
 {"name":"Waystation Rhythm","seq":(1,2,1,3,2,2,4,3,1)}]
def advance(s,a,x,check=True):
 phase,period,recent,counter,memory,interrupted=s
 if a in (1,2):
  kind=a-1;recent=(recent+(kind,))[-2:];punished=len(recent)==2 and recent[0]==recent[1];phase=(phase+period+kind+int(punished))%12;counter+=int(punished);memory=memory+(phase,)
 elif a==3:period=2+(period-1)%3
 elif a==4:phase=0
 elif a==5:
  if check and (phase!=x["window"] or not memory):return None
  interrupted=(phase,period,counter,len(memory),tuple(recent))
 return phase,period,recent,counter,memory,interrupted
for x in LEVELS:
 s=(0,2,(),0,(),None)
 for a in x["seq"]:s=advance(s,a,x,False)
 x["window"]=s[0];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,2,(),0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND
  for i in range(12):x=7+(i%6)*9;y=10+(i//6)*12;f[y:y+5,x:x+5]=WALKER if i==g.phase else TRACK
  wx=7+(g.cfg["window"]%6)*9;wy=10+(g.cfg["window"]//6)*12;f[wy+6:wy+9,wx:wx+5]=WINDOW
  f[38:43,8:8+g.period*10]=PERIOD
  for i,v in enumerate(g.recent):f[48:53,8+i*13:18+i*13]=MACRO0 if v==0 else MACRO1
  if g.counter:f[54:58,8:8+min(g.counter,5)*9]=HISTORY
  if g.interrupted:f[55:59,42:56]=WINDOW
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q785(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q785",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=0;self.period=2;self.recent=();self.counter=0;self.memory=();self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.phase,self.period,self.recent,self.counter,self.memory,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.phase,self.period,self.recent,self.counter,self.memory,self.interrupted=s
  elif a==6:
   if (self.phase,self.period,self.recent,self.counter,self.memory,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
