"""q774 Honeycomb Rhythm -- use local chunks to reach outer-clock interruption windows."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,PULSE,LOCAL,OUTER,WINDOW,INTERRUPT,BAD=2,6,4,9,11,13,7,10,15
LEVELS=[
 {"name":"Single Pulse","cycle":3,"window":1,"outer":0,"plan":(1,4,5)},
 {"name":"Double Pulse","cycle":3,"window":2,"outer":0,"plan":(2,4,5)},
 {"name":"Whole Routine","cycle":3,"window":0,"outer":1,"plan":(3,4,5)},
 {"name":"Chunk Then Interval","cycle":4,"window":2,"outer":1,"plan":(3,2,4,5)},
 {"name":"Two Outer Turns","cycle":5,"window":1,"outer":2,"plan":(3,3,1,4,5)},
 {"name":"Honeycomb Rhythm","cycle":4,"window":3,"outer":3,"plan":(3,3,3,2,1,4,5)}]
def tick(local,outer,events,n,cycle):
 total=local+n;wraps=total//cycle;return total%cycle,(outer+wraps)%4,events+wraps
def advance(s,a,x):
 local,outer,events,window,interrupted=s
 if a==1:local,outer,events=tick(local,outer,events,1,x["cycle"])
 elif a==2:local,outer,events=tick(local,outer,events,2,x["cycle"])
 elif a==3:local,outer,events=tick(local,outer,events,x["cycle"],x["cycle"])
 elif a==4:
  if local!=x["window"] or outer!=x["outer"]:return None
  window=(local,outer,events)
 elif a==5:
  if window is None:return None
  interrupted=(local,outer,events,window)
 return local,outer,events,window,interrupted
def target(x):
 s=(0,0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE
  for yi,y in enumerate((8,20,32)):
   for xi,x in enumerate((8,20,32,44)):f[y:y+8,x:x+9]=CELL+(xi+yi)%2
  f[41:44,8:56]=PULSE
  f[10:15,8:8+g.local*11]=LOCAL;f[23:28,8:8+g.outer*11]=OUTER;f[36:40,8:8+min(g.events,6)*8]=PULSE
  if g.window:f[44:49,8:56]=WINDOW
  if g.interrupted:f[52:57,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q774(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q774",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.outer=self.events=0;self.window=self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.outer,self.events,self.window,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.outer,self.events,self.window,self.interrupted=s
  elif a==6:
   if (self.local,self.outer,self.events,self.window,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
