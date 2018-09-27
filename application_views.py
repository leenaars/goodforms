# -*- coding: UTF-8 -*-
# Copyright (C) 2010 Hervé Cauwelier <herve@itaapy.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

# Import from the Standard Library
import traceback
from urllib import quote

# Import from itools
from itools.core import is_prototype, freeze
from itools.datatypes import String
from itools.gettext import MSG
from itools.handlers.utils import transmap
from itools.web import INFO, ERROR, BaseView, get_context

# Import from ikaaro
from ikaaro.autoadd import AutoAdd
from ikaaro.autoedit import AutoEdit
from ikaaro.folder_views import GoToSpecificDocument

# Import from agitools
from agitools.autotable import AutoTable

# Import from goodforms
from buttons import ExportODSButton, ExportXLSButton
from form import Form
from rw import ODSWriter, XLSWriter
from utils import force_encode, FormatError
from workflow import WorkflowState, NOT_REGISTERED
from customization import custom_flag


ERR_NO_DATA = ERROR(u"No data to collect for now.")
ERR_NO_MORE_ALLOWED = ERROR(u'You have reached the maximum allowed users. <a href="./;order">Buy new credits</a> if you want to add more users.', format='html')
INFO_NEW_APPLICATION = INFO(u'Your application is created. You are now on the test form.')
ERR_PASSWORD_MISSING = ERROR(u"The password is missing.")
ERR_BAD_EMAIL = ERROR(u"The given username is not an e-mail address.")
ERR_SUBSCRIPTION_FULL = ERROR(u"No more users are allowed to register.")
ERR_NOT_ALLOWED = ERROR(u"You are not allowed to register.")
ERR_ALREADY_REGISTERED = ERROR(u"You are already registered. Log in using your password.")
MSG_APPLICATION_TITLE = MSG(u'<span class="application-title">Title of your application:</span> {title}', format='replace_html')
MAILTO_SUBJECT = MSG(u'{workgroup_title}, form "{application_title}"')
MAILTO_BODY = MSG(u'Please fill in the form "{application_title}" available here:\r\n <{application_url}>.\r\n')




class Application_NewInstance(AutoAdd):

    fields = ['title', 'data']
    goto_view = None
    automatic_resource_name = True

    def action(self, resource, context, form):
        child = self.make_new_resource(resource, context, form)
        if child is None:
            return
        try:
            child._load_from_file(form['data'], context)
        except ValueError, e:
            context.message = ERROR(u'Cannot load: {x}').gettext(x=unicode(e))
            return
        except Exception:
            # FIXME (just for debug)
            print traceback.format_exc()
            pass
        goto = str(child.abspath)
        return context.come_back(INFO_NEW_APPLICATION, goto)



class Application_View(AutoTable):

    access = 'is_allowed_to_edit'
    title = MSG(u"Manage your Data Collection Application")
    #template = '/ui/goodforms/application/view.xml'

    # Search Form
    search_schema = {}
    search_fields = []

    # Configuration
    base_classes = Form.class_id

    # FIXME
    #search_template = '/ui/goodforms/application/search.xml'

    # Table
    table_fields = ['name', 'state', 'mtime', 'firstname', 'lastname', 'company', 'email']

    # FIXME
    table_actions = []
    #table_actions = freeze([ExportODSButton, ExportXLSButton])


    def get_page_title(self, resource, context):
        title = resource.get_page_title()
        return MSG_APPLICATION_TITLE.gettext(title=title)



    def get_item_value(self, resource, context, item, column):
        brain, item_resource = item
        if column == 'name':
            return (brain.name, context.get_link(item_resource))
        elif column in ('state', 'firstname', 'lastname', 'company',
                'email'):
            user = context.root.get_user(brain.name)
            if column == 'state':
                if user is not None and not user.get_value('password'):
                    return WorkflowState.get_value(NOT_REGISTERED)
                return 'XXX'
            elif column in ('firstname', 'lastname', 'company'):
                if user is None:
                    return u""
                return user.get_value(column)
            elif column == 'email':
                if user is None:
                    return u""
                email = user.get_value('email')
                application_title = resource.get_title()
                subject = MAILTO_SUBJECT.gettext(
                        workgroup_title=resource.parent.get_title(),
                        application_title=application_title)
                subject = quote(subject.encode('utf8'))
                application_url = resource.get_spread_url(context, email)
                body = MAILTO_BODY.gettext(
                        application_title=application_title,
                        application_url=application_url)
                body = quote(body.encode('utf8'))
                url = 'mailto:{0}?subject={1}&body={2}'.format(email,
                        subject, body)
                return (email, url)
        proxy = super(Application_View, self)
        return proxy.get_item_value(resource, context, item, column)



    def get_key_sorted_by_name(self):
        def key(item):
            return int(item.name)
        return key


    def get_key_sorted_by_state(self):
        get_user = get_context().root.get_user
        def key(item, cache={}):
            name =  item.name
            if name in cache:
                return cache[name]
            user = get_user(name)
            if user is not None and not user.get_value('password'):
                state = NOT_REGISTERED
            else:
                state = item.workflow_state
            title = WorkflowState.get_value(state)
            value = title.gettext().lower().translate(transmap)
            cache[name] = value
            return value
        return key


    def get_key_sorted_by_user(self):
        get_user = get_context().root.get_user
        def key(item, cache={}):
            name = item.name
            if name in cache:
                return cache[name]
            user = get_user(name)
            if user is None:
                value = None
            else:
                value = user.get_title().lower().translate(transmap)
            cache[name] = value
            return value
        return key


    def get_key_sorted_by_email(self):
        get_user = get_context().root.get_user
        def key(item, cache={}):
            name = item.name
            if name in cache:
                return cache[name]
            user = get_user(name)
            if user is None:
                value = None
            else:
                email = user.get_value('email').lower()
                # Group by domain
                username, domain = email.split('@')
                value = (domain, username)
            cache[name] = value
            return value
        return key


    #def get_search_namespace(self, resource, context):
    #    namespace = {}
    #    namespace['state_widget'] = SelectWidget('search_state',
    #            datatype=WorkflowState, value=context.query['search_state'])
    #    return namespace


    #def get_namespace(self, resource, context):
    #    namespace = {}
    #    namespace['menu'] = resource.menu.GET(resource, context)
    #    namespace['n_forms'] = resource.get_n_forms()
    #    namespace['max_users'] = resource.get_value('max_users')
    #    namespace['spread_url'] = resource.get_spread_url(context)

    #    # Search
    #    search_template = resource.get_resource(self.search_template)
    #    search_namespace = self.get_search_namespace(resource, context)
    #    namespace['search'] = stl(search_template, search_namespace)

    #    # Batch
    #    results = self.get_items(resource, context)
    #    query = context.query
    #    if results or query['search_state'] or query['search_term']:
    #        template = resource.get_resource(self.batch_template)
    #        batch_namespace = self.get_batch_namespace(resource, context,
    #                results)
    #        namespace['batch'] = stl(template, batch_namespace)
    #    else:
    #        namespace['batch'] = None

    #    # Table
    #    if results:
    #        items = self.sort_and_batch(resource, context, results)
    #        template = resource.get_resource(self.table_template)
    #        table_namespace = self.get_table_namespace(resource, context,
    #                items)
    #        namespace['table'] = stl(template, table_namespace)
    #    else:
    #        namespace['table'] = None

    #    return namespace


    def action_export(self, resource, context, form, writer_cls=ODSWriter):
        name = MSG(u"{title} Users").gettext(title=resource.get_title())
        writer = writer_cls(name)

        header = [title.gettext() for column, title in self.table_columns]
        writer.add_row(header, is_header=True)
        results = self.get_items(resource, context)
        context.query['batch_size'] = 0
        for item in self.sort_and_batch(resource, context, results):
            row = []
            for column, title in self.table_columns:
                if column == 'state':
                    item_brain, item_resource = item
                    user = context.root.get_user(item_brain.name)
                    if (user is not None
                            and user.get_value('password') is None):
                        state = NOT_REGISTERED
                    else:
                        state = item_brain.workflow_state
                    value = WorkflowState.get_value(state)
                else:
                    value = self.get_item_value(resource, context, item,
                            column)
                if type(value) is tuple:
                    value = value[0]
                if type(value) is unicode:
                    pass
                elif is_prototype(value, MSG):
                    value = value.gettext()
                elif type(value) is str:
                    value = unicode(value)
                else:
                    raise NotImplementedError, str(type(value))
                row.append(value)
            writer.add_row(row)

        body = writer.to_str()

        context.set_content_type(writer_cls.mimetype)
        context.set_content_disposition('attachment',
                filename="{0}-users.{1}".format(resource.name,
                    writer_cls.extension))

        return body


    def action_export_xls(self, resource, context, form):
        return self.action_export(resource, context, form,
                writer_cls=XLSWriter)



class Application_Export(BaseView):
    access = 'is_allowed_to_edit'
    title = MSG(u"Export Collected Data")
    query_schema = freeze({
        'format': String})


    def GET(self, resource, context):
        for form in resource.get_forms():
            state = form.get_workflow_state()
            if state != 'private':
                break
        else:
            return context.come_back(ERR_NO_DATA)

        format = context.query['format']
        if format == 'xls':
            writer_cls = XLSWriter
        else:
            writer_cls = ODSWriter
        name = MSG(u"{title} Data").gettext(title=resource.get_title())
        writer = writer_cls(name)

        schema_resource = resource.get_resource('schema')
        schema, pages = schema_resource.get_schema_pages()
        # Main header
        header = [title.gettext()
                for title in (MSG(u"Form"), MSG(u"First Name"),
                    MSG(u"Last Name"), MSG(u"E-mail"), MSG(u"State"))]
        for name in sorted(schema):
            header.append(name.replace('_', ''))
        try:
            writer.add_row(header, is_header=True)
        except FormatError, exception:
            return context.come_back(ERROR(unicode(exception)))
        # Subheader with titles
        header = [""] * 5
        for name, datatype in sorted(schema.iteritems()):
            header.append(datatype.title)
        writer.add_row(header, is_header=True)
        # optionnaly add a header in results with goodforms type for each column:
        if custom_flag('header_data_type'):
            header = [""] * 5
            for name, datatype in sorted(schema.iteritems()):
                header.append(datatype.type)
            writer.add_row(header, is_header=True)
        users = resource.get_resource('/users')
        for form in resource.get_forms():
            user = users.get_resource(form.name, soft=True)
            if user:
                get_value = user.get_value
                email = get_value('email')
                firstname = get_value('firstname')
                lastname = get_value('lastname')
            else:
                email = ""
                firstname = ""
                lastname = form.name
            state = WorkflowState.get_value(form.get_workflow_state())
            state = state.gettext()
            row = [form.name, firstname, lastname, email, state]
            handler = form.handler
            for name, datatype in sorted(schema.iteritems()):
                value = handler.get_value(name, schema)
                if datatype.multiple:
                    value = '\n'.join(value.decode('utf-8')
                            for value in datatype.get_values(value))
                else:
                    data = force_encode(value, datatype, 'utf_8')
                    value = unicode(data, 'utf_8')
                row.append(value)
            writer.add_row(row)

        body = writer.to_str()

        context.set_content_type(writer.mimetype)
        context.set_content_disposition('attachment',
                filename="{0}.{1}".format(resource.name, writer.extension))

        return body





class Application_Edit(AutoEdit):

    fields = ['title']



class Application_RedirectToForm(GoToSpecificDocument):
    access = 'is_allowed_to_view'
    title = MSG(u"Show Test Form")


    def get_form_name(self, user, resource):
        root = resource.get_resource('/')
        if root.is_allowed_to_edit(user, resource):
            return resource.default_form
        if resource.get_resource(user.name, soft=True) is not None:
            return user.name
        return None


    def get_specific_document(self, resource, context):
        return self.get_form_name(context.user, resource)
