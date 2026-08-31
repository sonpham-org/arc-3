"""q226 Crossing Veil -- schedule attention across capped docks and alternating controllers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PASSENGER,FOCUS,MARK,CONTROL,CAP,BAD=5,10,9,14,6,11,2,7,15
LEVELS=[{"name":"First Dock","capacity":2,"plan":(1,4)},{"name":"Hidden Passenger","capacity":2,"plan":(2,1,5,4)},{"name":"Remote Mark","capacity":3,"plan":(3,4,5,2,4)},{"name":"Split Control","capacity":3,"plan":(1,5,2,4,3)},{"name":"Capacity Veil","capacity":4,"plan":(2,4,5,3,1,4)},{"name":"Crossing Veil","capacity":4,"plan":(3,5,1,4,2,5,3,4)}]
def advance(s,a,x):
 passengers,focus,controller,marks=s;passengers=list(passengers);marks=list(marks);cap=x["capacity"]
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:passengers[i]=(passengers[i]+controller+i+1)%(cap+1)
 elif a==4:marks[controller]=(passengers[focus]+focus+controller)%4
 elif a==5:controller=1-controller
 return tuple(passengers),focus,controller,tuple(marks)
def target(x):
 s=((0,1,2),0,0,(0,0))
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=RIVER
  for i,v in enumerate(g.passengers):px=8+i*18;f[9:37,px:px+14]=DOCK;f[31-v*5:36-v*5,px+4:px+10]=PASSENGER-i
  f[7:10,8+g.focus*18:22+g.focus*18]=FOCUS;f[42:45,8:11+g.marks[0]*11]=MARK;f[47:50,8:11+g.marks[1]*11]=MARK;f[53:56,8:11+g.controller*22]=CONTROL;f[58:60,8:11+x["capacity"]*10]=CAP
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q226(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q226",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.passengers=(0,1,2);self.focus=self.controller=0;self.marks=(0,0)
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.passengers,self.focus,self.controller,self.marks=advance((self.passengers,self.focus,self.controller,self.marks),a,x)
  elif a==6:
   if (self.passengers,self.focus,self.controller,self.marks)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
