"""q386 Palimpsest Delegation -- integrate two partial views using a visible near miss."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,VIEW,MARK,EXAMPLE,INTEGRATE,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"Two Readers","shift":1,"plan":(1,3,4,2,3,5)},{"name":"Crossed Shelves","shift":2,"plan":(2,3,4,1,3,5)},{"name":"Overlapping Notes","shift":3,"plan":(1,2,3,4,2,3,5)},{"name":"Paired Near Miss","shift":1,"plan":(2,1,3,4,1,2,3,5)},{"name":"Rotating Custody","shift":2,"plan":(1,3,4,2,1,3,4,2,3,5)},{"name":"Palimpsest Delegation","shift":3,"plan":(2,1,3,4,1,3,2,4,2,1,3,5)}]
def advance(s,a,x):
 controller,views,marks,failed,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2):views.append((controller,a,(a+x["shift"]+controller)%4))
 elif a==3:
  mine=[v for v in views if v[0]==controller]
  if not mine:return None
  marks.append((controller,len(mine),sum(v[2] for v in mine)%4))
 elif a==4:controller=1-controller
 elif a==5:
  if len({m[0] for m in marks})<2:return None
  failed=(tuple(marks),x["shift"]);integrated=(sum((m[0]+1)*m[2] for m in marks)+x["shift"])%7
 return controller,tuple(views),tuple(marks),failed,integrated
def target(x):
 s=(0,(),(),None,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE;f[5:8,8:24]=MARK;f[5:8,40:56]=EXAMPLE
  f[8:31,7:29]=SHELF;f[8:31,35:57]=SHELF
  for i,(_,_,v) in enumerate(g.views[-8:]):x=10+(i%4)*5;y=12+(i//4)*11;f[y:y+6,x+g.controller*28:x+4+g.controller*28]=VIEW-v
  for i,m in enumerate(g.marks[-6:]):f[36+i*3:38+i*3,8:12+m[2]*11]=MARK
  f[54:57,8:24]=EXAMPLE if g.failed else TILE;f[54:57,40:56]=INTEGRATE if g.integrated else SHELF
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q386(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q386",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=();self.marks=();self.failed=None;self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.views,self.marks,self.failed,self.integrated),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.views,self.marks,self.failed,self.integrated=s
  elif a==6:
   if (self.controller,self.views,self.marks,self.failed,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
