"""a085 Buckle Line -- orient and brace slender columns under a press."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,COLUMN,WEAK,BRACE,PRESS,LOAD,BUCKLE,ORIENT,BAD=13,8,9,12,14,10,11,6,4,15
LEVELS=[
 {"name":"Rotate Column","seq":(1,)},{"name":"Select Column","seq":(2,)},
 {"name":"Add Brace","seq":(3,1)},{"name":"Press Stage","seq":(1,2,3,4,1)},
 {"name":"Unsupported Length","seq":(2,1,3,4,2,1,4)},{"name":"Buckle Line","seq":(1,2,3,4,2,1,3,4,1,4)},
]
def advance(s,a):
 orientation,braces,cursor,press,buckles,history,snapshot=s;o=list(orientation);b=list(braces)
 if a==1:o[cursor]^=1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%4;history=(history+(2,))[-8:]
 elif a==3:b[cursor]^=1;history=(history+(3,))[-8:]
 elif a==4:press=(press+1)%6;buckles=(buckles+sum(int(not o[i] and not b[i] and press>2) for i in range(4)))%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(o),tuple(b),cursor,press,buckles,history)
 return tuple(o),tuple(b),cursor,press,buckles,history,snapshot
for x in LEVELS:
 s=((0,1,0,1),(0,0,0,0),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8+g.press*3:15+g.press*3,6:58]=PRESS
  for i,v in enumerate(g.orientation):
   x=10+i*13;w=6 if v else 3;f[22:52,x:x+w]=COLUMN if v else WEAK
   if g.braces[i]:f[32:36,x-4:x+9]=BRACE
   if i==g.cursor:f[54:58,x-3:x+9]=ORIENT
  f[7:10,8:8+g.press*8]=LOAD
  for i in range(g.buckles):f[17:20,8+i*6:13+i*6]=BUCKLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A085(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a085",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.orientation,self.braces,self.cursor,self.press,self.buckles,self.history,self.snapshot=((0,1,0,1),(0,0,0,0),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.orientation,self.braces,self.cursor,self.press,self.buckles,self.history,self.snapshot=advance((self.orientation,self.braces,self.cursor,self.press,self.buckles,self.history,self.snapshot),a)
  elif a==6:
   if (self.orientation,self.braces,self.cursor,self.press,self.buckles,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
