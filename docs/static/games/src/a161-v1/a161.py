"""a161 Frontier Marks -- preserve scarce frontier state while passages disappear."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAZE,WALL,PASSAGE,MARKER,EXPLORER,CLOSED,FRONTIER,COVERED,REPEAT=13,8,7,10,14,12,6,11,4,9
BAD=15
LEVELS=[
 {"name":"Move Marker","seq":(1,)},{"name":"Select Marker","seq":(2,)},
 {"name":"Explore Branch","seq":(3,1)},{"name":"Remember Frontier","seq":(1,2,3,4,2)},
 {"name":"Close Subtree","seq":(1,3,2,1,4,3,2)},{"name":"Frontier Marks","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 markers,cursor,visited,closed,frontier,repeats,history,snapshot=s;m=list(markers)
 if a==1:m[cursor]=(m[cursor]+1)%12;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  node=m[cursor];repeats+=int((visited>>node)&1);visited|=1<<node;closed|=1<<((node-1)%12);frontier=sum(1<<p for p in m if not ((visited>>p)&1));history=(history+(3,))[-8:]
 elif a==4:history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(m),cursor,visited,closed,frontier,repeats,history)
 return tuple(m),cursor,visited,closed,frontier,repeats,history,snapshot
for q in LEVELS:
 s=((1,5,9),0,1,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAZE
  for i in range(12):
   x=8+(i%4)*13;y=10+(i//4)*15;f[y:y+11,x:x+11]=CLOSED if (g.closed>>i)&1 else COVERED if (g.visited>>i)&1 else PASSAGE
  for i,p in enumerate(g.markers):x=10+(p%4)*13;y=12+(p//4)*15;f[y:y+7,x:x+7]=EXPLORER if i==g.cursor else MARKER
  f[54:58,8:8+g.frontier.bit_count()*8]=FRONTIER;f[7:10,8:8+min(6,g.repeats)*7]=REPEAT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A161(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a161",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.markers,self.cursor,self.visited,self.closed,self.frontier,self.repeats,self.history,self.snapshot=((1,5,9),0,1,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.markers,self.cursor,self.visited,self.closed,self.frontier,self.repeats,self.history,self.snapshot=advance((self.markers,self.cursor,self.visited,self.closed,self.frontier,self.repeats,self.history,self.snapshot),a)
  elif a==6:
   if (self.markers,self.cursor,self.visited,self.closed,self.frontier,self.repeats,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
