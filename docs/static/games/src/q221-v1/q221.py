"""q221 Pollen Veil -- freeze one bloom while hidden kites follow a worn complement rule."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,KITE,WAVE,FOCUS,WEAR,GOAL,BAD=3,10,7,11,15,12,14,8
LEVELS=[{"name":"Frozen Bloom","plan":(1,4)},{"name":"Hidden Kite","plan":(2,1,4)},{"name":"Wear Cue","plan":(3,5,4,1)},{"name":"Complement Wave","plan":(1,5,2,4,3)},{"name":"Coupled Meadow","plan":(2,4,3,5,1,4)},{"name":"Pollen Veil","plan":(3,5,1,4,2,5,3,4)}]
def advance(s,a):
 kites,focus,worn,exposed=s;kites=list(kites)
 if a in (1,2,3):
  focus=a-1;exposed=True
  for i in range(3):
   if i!=focus:kites[i]=(kites[i]+(3-(i+1) if worn else i+1))%4
 elif a==4:kites[focus]=(kites[focus]+(3-focus if worn else focus+2))%4;exposed=False
 elif a==5:worn=not worn;kites=[3-v for v in kites]
 return tuple(kites),focus,worn,exposed
def target(x):
 s=((0,1,2),0,False,False)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MEADOW
  for i,v in enumerate(g.kites):x=8+i*18;f[10:20,x:x+13]=KITE;f[20:43,x+4:x+8]=WAVE;f[28+v*3:33+v*3,x+2:x+11]=KITE
  f[7:10,8+g.focus*18:21+g.focus*18]=FOCUS
  if g.worn:f[47:51,8:56]=WEAR
  f[54:58,8:8+sum(g.kites)*5]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q221(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.kites=(0,1,2);self.focus=0;self.worn=self.exposed=self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q221",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.kites=(0,1,2);self.focus=0;self.worn=self.exposed=self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.kites,self.focus,self.worn,self.exposed=advance((self.kites,self.focus,self.worn,self.exposed),a)
  elif a==6:
   if (self.kites,self.focus,self.worn,self.exposed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
