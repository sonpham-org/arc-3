"""a162 Survey Ribbon -- cover irregular boundaries with minimal retracing."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SEA,ISLAND,BOUNDARY,SCANNED,SCANNER,DOCK,BATTERY,RETRACE,COMPLETE=14,8,7,12,10,13,11,4,6,9
BAD=15
LEVELS=[
 {"name":"Scan Segment","seq":(1,)},{"name":"Move Scanner","seq":(2,)},
 {"name":"Change Island","seq":(3,1)},{"name":"Organize Survey","seq":(1,2,3,4,2)},
 {"name":"Avoid Retrace","seq":(1,3,2,1,4,3,2)},{"name":"Survey Ribbon","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 scanned,cursor,island,battery,retrace,coverage,history,snapshot=s
 if a==1:
  bit=1<<cursor;retrace+=int(bool(scanned&bit));battery=max(0,battery-(2 if scanned&bit else 1));scanned|=bit;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%16;history=(history+(2,))[-8:]
 elif a==3:island=(island+1)%3;cursor=(cursor+5)%16;history=(history+(3,))[-8:]
 elif a==4:coverage=scanned.bit_count();history=(history+(4,))[-8:]
 elif a==5:snapshot=(scanned,cursor,island,battery,retrace,coverage,history)
 return scanned,cursor,island,battery,retrace,coverage,history,snapshot
for q in LEVELS:
 s=(1,0,0,24,0,1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SEA;origins=((12,14),(38,13),(25,36))
  for x,y in origins:f[y:y+17,x:x+18]=ISLAND;f[y-3:y+20,x-3:x+21]=BOUNDARY;f[y:y+17,x:x+18]=ISLAND
  for i in range(16):
   x=7+(i%8)*7;y=8+(i//8)*43;f[y:y+4,x:x+5]=SCANNED if (g.scanned>>i)&1 else BOUNDARY
  x=7+(g.cursor%8)*7;y=8+(g.cursor//8)*43;f[y-3:y,x:x+5]=SCANNER;f[52:58,55:60]=DOCK;f[54:58,8:8+min(10,g.battery)*4]=BATTERY;f[7:10,8:8+g.retrace*6]=RETRACE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A162(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a162",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.scanned,self.cursor,self.island,self.battery,self.retrace,self.coverage,self.history,self.snapshot=(1,0,0,24,0,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.scanned,self.cursor,self.island,self.battery,self.retrace,self.coverage,self.history,self.snapshot=advance((self.scanned,self.cursor,self.island,self.battery,self.retrace,self.coverage,self.history,self.snapshot),a)
  elif a==6:
   if (self.scanned,self.cursor,self.island,self.battery,self.retrace,self.coverage,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
