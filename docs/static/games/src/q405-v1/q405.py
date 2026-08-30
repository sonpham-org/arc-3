"""q405 Vivarium Delegation -- alternate partial views, marks, and reciprocal help."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLASS,SOIL,FAUNA,HEAT,CONTROL,MARK,FAVOR,BAD=0,10,12,14,8,15,9,6,13
LEVELS=[
 {"name":"One Projection","plan":(1,3)},
 {"name":"Remote Mark","plan":(2,3,4,1)},
 {"name":"Alternating View","plan":(1,3,4,2,3)},
 {"name":"Fair Help","plan":(2,5,3,4,1,5)},
 {"name":"Reciprocity Rule","plan":(1,3,5,4,2,5,3)},
 {"name":"Vivarium Delegation","plan":(2,3,4,1,5,3,4,2,5,1)}]
def advance(s,a):
 layers,controller,knowledge,marks,favor=s;layers=list(layers);knowledge=list(knowledge);marks=list(marks)
 if a in (1,2):knowledge[controller]|=1<<((layers[controller]+a+controller)%4)
 elif a==3:marks[controller]=(knowledge[controller]+controller+1)%8
 elif a==4:controller=1-controller
 elif a==5:
  other=1-controller;fair=1 if marks[other] and marks[other]!=marks[controller] else 0;favor=(favor+fair+1)%4
  layers[controller]=(layers[controller]+favor+1)%4
 return tuple(layers),controller,tuple(knowledge),tuple(marks),favor
def target(x):
 s=((1,3),0,(0,0),(0,0),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:59,5:59]=GLASS
  for i,v in enumerate(g.layers):
   y=9+i*24;f[y:y+20,9:55]=SOIL;f[y+3+v*3:y+8+v*3,14:22]=FAUNA;f[y+4:y+10,39:49]=HEAT
   f[y+17:y+20,10:10+g.knowledge[i]*4]=CONTROL;f[y:y+3,10:10+g.marks[i]*5]=MARK
  f[55:59,8:8+g.favor*13]=FAVOR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q405(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q405",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.layers=(1,3);self.controller=0;self.knowledge=(0,0);self.marks=(0,0);self.favor=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.layers,self.controller,self.knowledge,self.marks,self.favor=advance((self.layers,self.controller,self.knowledge,self.marks,self.favor),a)
  elif a==6:
   if (self.layers,self.controller,self.knowledge,self.marks,self.favor)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
