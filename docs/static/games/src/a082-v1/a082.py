"""a082 Load Path -- redirect a roof force trace around weak members."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HALL,ROOF,MEMBER,WEAK,BRACE,FORCE,FOUNDATION,CURSOR,BAD=10,8,9,4,12,14,11,13,6,15
LEVELS=[
 {"name":"Select Cell","seq":(2,)},{"name":"Add Brace","seq":(1,)},
 {"name":"Trace Force","seq":(1,3)},{"name":"Avoid Weak Cell","seq":(2,1,2,1,3)},
 {"name":"Capacity Route","seq":(1,2,1,3,4,2,3)},{"name":"Load Path","seq":(2,1,3,2,1,4,3,1,2,3)},
]
def advance(s,a):
 braces,cursor,route,load,overload,history,snapshot=s;b=list(braces)
 if a==1:b[cursor]^=1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:
  path=[];node=0
  for row in range(3):node=(node+1+int(b[(cursor+row)%6]))%6;path.append(node)
  route=tuple(path);overload=(overload+sum(int(x in (2,5)) for x in path))%6;history=(history+(3,))[-8:]
 elif a==4:load=1+load%4;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),cursor,route,load,overload,history)
 return tuple(b),cursor,route,load,overload,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0),0,(),1,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HALL;f[9:16,7:57]=ROOF;f[50:56,7:57]=FOUNDATION
  coords=((13,20),(29,20),(45,20),(13,35),(29,35),(45,35))
  for i,(x,y) in enumerate(coords):
   f[y:y+12,x:x+7]=WEAK if i in (2,5) else MEMBER
   if g.braces[i]:f[y+2:y+8,x+8:x+14]=BRACE
   if i==g.cursor:f[y-4:y-1,x:x+12]=CURSOR
  for i,node in enumerate(g.route):x,y=coords[node];f[y+3:y+8,x+2:x+5]=FORCE
  for i in range(g.overload):f[55:58,8+i*6:13+i*6]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A082(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a082",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.braces,self.cursor,self.route,self.load,self.overload,self.history,self.snapshot=((0,0,0,0,0,0),0,(),1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.braces,self.cursor,self.route,self.load,self.overload,self.history,self.snapshot=advance((self.braces,self.cursor,self.route,self.load,self.overload,self.history,self.snapshot),a)
  elif a==6:
   if (self.braces,self.cursor,self.route,self.load,self.overload,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
